import numpy as np
import matplotlib.pyplot as plt
from fmpy import read_model_description, extract
from fmpy.fmi2 import FMU2Slave, FMICallException
import tempfile, shutil, sys, contextlib, os
from _JADE import JADE
import torch
import time
import multiprocessing as mp
import sys
# ────────────────────────────────────────────────────────────────────────────
@contextlib.contextmanager
def redirect_stdout_stderr():
    with open(os.devnull, 'w') as devnull:
        old_stdout, old_stderr = sys.stdout, sys.stderr
        try:
            sys.stdout = sys.stderr = devnull
            yield
        finally:
            sys.stdout, sys.stderr = old_stdout, old_stderr

FMU = 'data/fmu_edit.fmu'
EXTRACT_DIR = extract(FMU, tempfile.mkdtemp())
prices_file = np.loadtxt('data/prices_weather.txt')
prices_file = prices_file[::2]
price_times = prices_file[:, 0]
price_values = prices_file[:, -1]

STEPS_SECONDS = 1800
ITER_ = int(STEPS_SECONDS / 60)
T0 = 0.0
STEP_SEC = STEPS_SECONDS
TEND = 365 * 24 * 3600
BLOCK = 48
hours = 24
horizon = hours * 2
total_steps = int(TEND / STEP_SEC)
swarm = 96
swarm_low_res = 48


exploratory_soc_horizon = 2 
elite_warm_start = False

max_evals_default = 10000
max_evals_low_res_default = 4000

max_evals_init = 25000
max_evals_low_res_init = 4000

n_runs = 1
base_results_dir = "optimal_control_results"


def make_fmu():
    md = read_model_description(FMU)
    fmu = FMU2Slave(guid=md.guid,
                    unzipDirectory=EXTRACT_DIR,
                    modelIdentifier=md.coSimulation.modelIdentifier)
    fmu.instantiate()
    vr = {v.name: v.valueReference for v in md.modelVariables}
    fmu.setReal([vr['bat.etaCha'], vr['bat.etaDis']], [0.95, 0.95])
    return fmu, vr

def get_24h_price_projection(current_step):
    start_idx = current_step
    end_idx = start_idx + 48
    return price_values[start_idx:end_idx]

def save_state(fmu):
    st = fmu.getFMUstate()
    ser = fmu.serializeFMUstate(st)
    fmu.freeFMUstate(st)
    return ser

def load_state(fmu, ser):
    st = fmu.deSerializeFMUstate(ser)
    fmu.setFMUstate(st)
    fmu.freeFMUstate(st)


def projection(raw_pcharge, prev_soc, step_seconds):
    BATTERY_CAPACITY_KWH = 1124.8
    ETA = 0.95
    dt_h = step_seconds / 3600.0
    max_ch = (1 - prev_soc) * BATTERY_CAPACITY_KWH / (dt_h * ETA)
    max_di = prev_soc * BATTERY_CAPACITY_KWH * ETA / dt_h
    p_kw = raw_pcharge * (max_ch if raw_pcharge >= 0 else max_di)
    return float(np.clip(p_kw * 1000., -400e3, 400e3))

def daytime_penalty(t, qprod_MW):
    tod = round(t) % 86400
    if 8*3600 <= tod <= 20*3600:
        return 1000 * max(0.0, 0.999 - qprod_MW)
    return 0.0

def run_horizon(u_mat, state0, cost0, t0, terminal_soc_target, terminal_tmedian_target, steps_seconds):
    fmu, vr = make_fmu()
    try:
        fmu.setupExperiment(startTime=t0)
        fmu.enterInitializationMode(); fmu.exitInitializationMode()
        load_state(fmu, state0)
        vr_in = [vr['pumboi'], vr['pumhea'], vr['Pcharge']]
        t = t0
        soc = fmu.getReal([vr['soc']])[0]
        pen = 0.0
        for pum_raw, pr_raw in u_mat:
            pum = 0.0 if pum_raw < 2.4 else pum_raw
            pbat = projection(pr_raw, soc, steps_seconds)
            fmu.setReal(vr_in, [0.0, pum, pbat])
            for _ in range(ITER_):
                with redirect_stdout_stderr():
                    fmu.doStep(t, 60)
                t += 60
            qprod, soc = fmu.getReal([vr['yqprod'], vr['soc']])
            pen += daytime_penalty(t, qprod / 1e6)
        cost = fmu.getReal([vr['costtot']])[0]
        delta_cost = cost - cost0
        #print (terminal_tavg_target, 'terminal tavg')
        
        tmedian = np.median([fmu.getReal([vr['tan.vol[%d].T' % i]])[0] for i in range(1,11)])

        soc_dev_penalty = abs(soc - terminal_soc_target) 
        if terminal_tmedian_target is not None:
            tmedian_dev_penalty = abs(tmedian - terminal_tmedian_target) 
        else:
            tmedian_dev_penalty = 0
        
        return delta_cost + pen + 5*tmedian_dev_penalty + 5000*soc_dev_penalty

    finally:
        fmu.freeInstance()
        
def run_horizon_low_res(u_mat, state0, cost0, t0, low_res_steps_seconds):
    fmu, vr = make_fmu()
    try:
        fmu.setupExperiment(startTime=t0)
        fmu.enterInitializationMode(); fmu.exitInitializationMode()
        load_state(fmu, state0)
        vr_in = [vr['pumboi'], vr['pumhea'], vr['Pcharge']]
        t = t0
        soc = fmu.getReal([vr['soc']])[0]
        pen = 0.0
        for pum_raw, pr_raw in u_mat:
            pum = 0.0 if pum_raw < 2.4 else pum_raw
            pbat = projection(pr_raw, soc, low_res_steps_seconds)
            fmu.setReal(vr_in, [0.0, pum, pbat])
            for _ in range(int(low_res_steps_seconds / 60)):
                with redirect_stdout_stderr():
                    fmu.doStep(t, 60)
                t += 60
            qprod, soc = fmu.getReal([vr['yqprod'], vr['soc']])
            pen += daytime_penalty(t, qprod / 1e6)
        cost = fmu.getReal([vr['costtot']])[0]
        delta_cost = cost - cost0
        return delta_cost + pen
        
    finally:
        fmu.freeInstance()



for run_id in range(1, n_runs + 1):
    print(f"\n========== Running optimization {run_id}/{n_runs} ==========\n")
    
    st = time.time()


    run_results_dir = f"{base_results_dir}_{run_id}"
    os.makedirs(run_results_dir, exist_ok=True)

    RESUME_FILE = os.path.join(run_results_dir, "optimal_control_start.txt")
    if os.path.exists(RESUME_FILE):
        print(f"--- Resuming optimization from file: {RESUME_FILE} ---")
        loaded_controls = np.loadtxt(RESUME_FILE)
        optimal_control = loaded_controls.tolist()
        current_step = len(optimal_control)
    else:
        print("--- Starting a new optimization from scratch (t=0) ---")
        optimal_control = []
        current_step = 0

    init_x = []
    last_price_seq = None

    while current_step < total_steps:


        current_price_seq = get_24h_price_projection(current_step)

        if last_price_seq is None:
            
            last_price_seq = current_price_seq
            
            if max_evals_init > 0:
                max_evals = max_evals_init
                max_evals_low_res = max_evals_low_res_init

            
        elif not np.allclose(current_price_seq, last_price_seq, 1e-8):
            print(f"Price profile changed at step {current_step} → reset init_x")
            init_x = []
            last_price_seq = current_price_seq
            if max_evals_init > 0:
                max_evals = max_evals_init
                max_evals_low_res = max_evals_low_res_init
        
        
        steps_left = total_steps - current_step
        H = min(horizon, steps_left)

        fmu, vr = make_fmu()
        fmu.setupExperiment(startTime=T0, stopTime=TEND)
        fmu.enterInitializationMode(); fmu.exitInitializationMode()
        past = np.vstack(optimal_control) if optimal_control else np.empty((0, 2))
        t = 0.0
        soc = fmu.getReal([vr['soc']])[0]
        for pum_raw, pr_raw in past:
            pum = 0.0 if pum_raw < 2.4 else pum_raw
            pbat = projection(pr_raw, soc, STEPS_SECONDS)
            fmu.setReal([vr['pumboi'], vr['pumhea'], vr['Pcharge']], [0.0, pum, pbat])
            for _ in range(ITER_):
                with redirect_stdout_stderr():
                    fmu.doStep(t, 60)
                t += 60
            soc = fmu.getReal([vr['soc']])[0]
        cost0 = fmu.getReal([vr['costtot']])[0]
        STATE0 = save_state(fmu)
        T0_snap = t
        fmu.freeInstance()
        
        """exploratory terminal soc"""
        
        if exploratory_soc_horizon > 0 and steps_left >= BLOCK * exploratory_soc_horizon:
        
            LOW_RES_STEP_SEC = 2 * 3600  # 2 h per step
            low_res_steps = int((exploratory_soc_horizon * 24 * 3600) / LOW_RES_STEP_SEC)  
        
            lb_expl = np.zeros(2 * low_res_steps)
            ub_expl = np.zeros(2 * low_res_steps)
            lb_expl[:low_res_steps] = 0;  ub_expl[:low_res_steps] = 12.0
            lb_expl[low_res_steps:] = -1.0;  ub_expl[low_res_steps:] = 1.0
            
            
            def _one_cost_low_res(x, state, c0, t0, LOW_RES_STEP_SEC):
                try:
                    u = np.column_stack((x[:low_res_steps], x[low_res_steps:]))
                    return run_horizon_low_res(u, state, c0, t0, LOW_RES_STEP_SEC)
                except FMICallException: return 1e12
                
            def obj_low_res_batch(X_batch):
                with mp.Pool(processes=os.cpu_count()) as pool:
                    jobs = [(x, STATE0, cost0, T0_snap, LOW_RES_STEP_SEC) for x in X_batch]
                    return np.array(pool.starmap(_one_cost_low_res, jobs), dtype=np.float32)
            
        
            opt_low = JADE(function=obj_low_res_batch,
                           lb=lb_expl, ub=ub_expl,
                           population_size=swarm_low_res,
                           max_evals=max_evals_low_res,
                           initial_X=[],
                           device='cpu')
        
            best_x_low, _, _ = opt_low.search()
        
            term_soc_u = np.column_stack((best_x_low[:low_res_steps], best_x_low[low_res_steps:]))
            fmu_term, vr_term = make_fmu()
            fmu_term.setupExperiment(startTime=T0_snap)
            fmu_term.enterInitializationMode(); fmu_term.exitInitializationMode()
            load_state(fmu_term, STATE0)
        
            soc_term = fmu_term.getReal([vr_term['soc']])[0]
            #t_avg = np.mean(t_terms)
            vr_in_term = [vr_term['pumboi'], vr_term['pumhea'], vr_term['Pcharge']]
            t_temp = T0_snap
        
            steps_in_first_day = int((24 * 3600) / LOW_RES_STEP_SEC)
            for pum_raw, pr_raw in term_soc_u[:steps_in_first_day]:
                pum = 0.0 if pum_raw < 2.4 else pum_raw
                pbat = projection(pr_raw, soc_term, LOW_RES_STEP_SEC)
                fmu_term.setReal(vr_in_term, [0.0, pum, pbat])
                for _ in range(int(LOW_RES_STEP_SEC / 60)):
                    with redirect_stdout_stderr():
                        fmu_term.doStep(t_temp, 60)
                    t_temp += 60
                soc_term = fmu_term.getReal([vr_term['soc']])[0]

            t_median_term = np.median([fmu_term.getReal([vr_term['tan.vol[%d].T' % i]])[0] for i in range(1,11)])

        
            fmu_term.freeInstance()
            terminal_soc = soc_term
            terminal_tmedian = t_median_term
            print(f"Exploratory terminal SoC target (Day 1): {terminal_soc:.4f}")
            print(f"Exploratory terminal Tavg target (Day 1): {terminal_tmedian:.4f}")
            #sys.exit()
        else:
            terminal_soc = 0
            terminal_tmedian = None

        if current_step < BLOCK:
            terminal_soc = 0
            terminal_tmedian = None
                    
            
        """high resolution controller"""

        lb = np.zeros(2 * H)
        ub = np.zeros(2 * H)
        lb[:H] = 0; ub[:H] = 12.0
        lb[H:] = -1.0; ub[H:] = 1.0

            
        def _one_cost(x, state, c0, t0, term_soc, term_tmedian, STEPS_SECONDS):
            try:
                u = np.column_stack((x[:H], x[H:]))
                return run_horizon(u, state, c0, t0, term_soc, term_tmedian, STEPS_SECONDS)
            except FMICallException:
                return 1e12

        def obj_batch(X_batch):
            with mp.Pool(processes=os.cpu_count()) as pool:
                jobs = [(x, STATE0, cost0, T0_snap, terminal_soc, terminal_tmedian, STEPS_SECONDS) for x in X_batch]
                return np.array(pool.starmap(_one_cost, jobs), dtype=np.float32)

        device = 'cpu'
        max_evals = max_evals
        swarm = swarm

        opt = JADE(function=obj_batch,
                   lb=lb, ub=ub,
                   population_size=swarm,
                   max_evals=max_evals,
                   initial_X=init_x,
                   device=device)
        
        best_x, best_pop, _ = opt.search()

        design = best_x
        if elite_warm_start and current_step > BLOCK:

            if len(init_x) == 0:
                init_x = design.copy().reshape(1, -1)
            else:
                init_x = np.vstack((init_x, design))
                if init_x.shape[0] > swarm:
                    init_x = init_x[-swarm:]

        accepted = min(BLOCK, H)
        for k in range(accepted):
            pum = design[k]
            pch = design[H + k]
            optimal_control.append([0.0 if pum < 2.4 else pum, pch])


        np.savetxt(os.path.join(run_results_dir, f"optimal_control_{current_step}.txt"), optimal_control)
        current_step += accepted
        print(f"[Run {run_id}] step {current_step:3d}/{total_steps-1}")
        if max_evals_init > 0 and max_evals == max_evals_init:
            max_evals = max_evals_default
        if max_evals_low_res_init > 0 and max_evals_low_res == max_evals_low_res_init:
            max_evals_low_res = max_evals_low_res_default

    optimal_control_array = np.vstack(optimal_control)
    np.save(os.path.join(run_results_dir, "optimal_control.npy"), optimal_control_array)
    print(f"Finished run {run_id}. optimal_control.shape = {optimal_control_array.shape}")
    
    et = np.abs(time.time() - st)

print ('Total run time: ', et)
