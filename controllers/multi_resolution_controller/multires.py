import numpy as np
from fmpy import read_model_description, extract
from fmpy.fmi2 import FMU2Slave, FMICallException
import tempfile, sys, contextlib, os
from _JADE import JADE
import multiprocessing as mp
import copy

@contextlib.contextmanager
def redirect_stdout_stderr():
    with open(os.devnull, 'w') as devnull:
        old_stdout, old_stderr = sys.stdout, sys.stderr
        try:
            sys.stdout = sys.stderr = devnull
            yield
        finally:
            sys.stdout, sys.stderr = old_stdout, old_stderr

# === Config ===
FMU = 'data/fmu_edit.fmu'
EXTRACT_DIR = extract(FMU, tempfile.mkdtemp())
prices_file = np.loadtxt('data/prices_weather.txt')
prices_file = prices_file[::2]
price_values = prices_file[:, -1]
weather_values = prices_file[:, 1]

# Step sizes
STEPS_SECONDS = 1800   # High-res: 30 min
LF_STEP_SECONDS = 3600 # Low/mid-res: 1h
EXPL_STEP_SECONDS = 7200 # Exploratory: 2h

ITER_ = int(STEPS_SECONDS/60)

T0 = 0.0
TEND = 365*24*3600
BLOCK = 48
hours = 24
horizon = hours * 2
total_steps = int(TEND / STEPS_SECONDS)

# Population sizes and eval budgets
swarm_HF = 96
swarm_LF = 96
swarm_expl = 48

max_evals_default_HF = 5000
max_evals_default_LF = 5000
max_evals_default_expl = 4000

max_evals_init_HF = 20000
max_evals_init_LF = 5000
max_evals_init_expl = 4000

exploratory_soc_horizon = 2
elite_warm_start = True

n_runs = 1
base_results_dir = "optimal_control_results"


def get_24h_price_projection(current_step):
    return price_values[current_step:current_step + 48]

def make_fmu():
    md = read_model_description(FMU)
    fmu = FMU2Slave(
        guid=md.guid,
        unzipDirectory=EXTRACT_DIR,
        modelIdentifier=md.coSimulation.modelIdentifier
    )
    fmu.instantiate()
    vr = {v.name: v.valueReference for v in md.modelVariables}
    fmu.setReal([vr['bat.etaCha'], vr['bat.etaDis']], [0.95, 0.95])
    return fmu, vr

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
    if 8 * 3600 <= tod <= 20 * 3600:
        return 1000 * max(0.0, 0.999 - qprod_MW)
    return 0.0

def run_horizon(u_mat, state0, cost0, t0, step_seconds, terminal_soc_target=None):
    fmu, vr = make_fmu()
    try:
        fmu.setupExperiment(startTime=t0)
        fmu.enterInitializationMode(); fmu.exitInitializationMode()
        load_state(fmu, state0)
        vr_in = [vr['pumboi'], vr['pumhea'], vr['Pcharge']]
        t = t0
        soc = fmu.getReal([vr['soc']])[0]
        pen = 0.0
        iter_steps = int(step_seconds / 60)
        for pum_raw, pr_raw in u_mat:
            pum = 0.0 if pum_raw < 2.4 else pum_raw
            pbat = projection(pr_raw, soc, step_seconds)
            fmu.setReal(vr_in, [0.0, pum, pbat])
            for _ in range(iter_steps):
                with redirect_stdout_stderr():
                    fmu.doStep(t, 60)
                t += 60
            qprod, soc = fmu.getReal([vr['yqprod'], vr['soc']])
            pen += daytime_penalty(t, qprod / 1e6)
        cost = fmu.getReal([vr['costtot']])[0]
        delta_cost = cost - cost0
        if terminal_soc_target is not None:
            delta_cost += 5000 * abs(soc - terminal_soc_target)
        return delta_cost + pen
    finally:
        fmu.freeInstance()

# --- Main run loop ---
for run_id in range(1, n_runs + 1):
    print(f"\n========== Running optimization {run_id}/{n_runs} ==========\n")
    run_results_dir = f"{base_results_dir}_{run_id}"
    os.makedirs(run_results_dir, exist_ok=True)

    RESUME_FILE = os.path.join(run_results_dir, f"optimal_control_start.txt")
    if os.path.exists(RESUME_FILE):
        print(f"--- Resuming optimization from file: {RESUME_FILE} ---")
        loaded_controls = np.loadtxt(RESUME_FILE)
        optimal_control = loaded_controls.tolist()
        current_step = len(optimal_control)
    else:
        print("--- Starting a new optimization from scratch (t=0) ---")
        optimal_control = []
        current_step = 0

    last_price_seq = None
    elite_pool = np.empty((0, 2*horizon))

    # Current eval budgets
    max_evals_HF = max_evals_default_HF
    max_evals_LF = max_evals_default_LF
    max_evals_expl = max_evals_default_expl

    while current_step < total_steps:
        current_price_seq = get_24h_price_projection(current_step)

        if last_price_seq is None or not np.allclose(current_price_seq, last_price_seq, 1e-8) or current_step <  BLOCK:
            if last_price_seq is not None:
                print(f"Price profile changed at step {current_step} → reset warm start")
                elite_pool = np.empty((0, 2*horizon))
            last_price_seq = current_price_seq
            max_evals_HF = max_evals_init_HF
            max_evals_LF = max_evals_init_LF
            max_evals_expl = max_evals_init_expl

        steps_left = total_steps - current_step
        H = min(horizon, steps_left)

        # --- Snapshot FMU state ---
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
        #STATE0 = save_state(fmu)
        try:
            STATE0 = save_state(fmu)
        except FMICallException:
            print(f"[WARN] Snapshot failed at step {current_step}, reinitializing FMU to rebuild state...")
            fmu.freeInstance()
            fmu, vr = make_fmu()
            fmu.setupExperiment(startTime=T0, stopTime=TEND)
            fmu.enterInitializationMode()
            fmu.exitInitializationMode()

            # Replay past controls to rebuild state
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

        # === Exploratory SOC target ===
        if exploratory_soc_horizon > 0:
            low_res_steps = int((exploratory_soc_horizon * 24 * 3600) / EXPL_STEP_SECONDS)
            lb_expl = np.zeros(2 * low_res_steps)
            ub_expl = np.zeros(2 * low_res_steps)
            lb_expl[:low_res_steps] = 0; ub_expl[:low_res_steps] = 12.0
            lb_expl[low_res_steps:] = -1.0; ub_expl[low_res_steps:] = 1.0

            def _one_cost_expl(x, state, c0, t0):
                try:
                    u = np.column_stack((x[:low_res_steps], x[low_res_steps:]))
                    return run_horizon(u, state, c0, t0, EXPL_STEP_SECONDS)
                except FMICallException:
                    return 1e6

            def obj_batch_expl(X_batch):
                state_copy_list = [copy.deepcopy(STATE0) for _ in range(len(X_batch))]
                with mp.Pool(processes=os.cpu_count()) as pool:
                    jobs = [(x, state_copy_list[i], cost0, T0_snap) for i, x in enumerate(X_batch)]
                    return np.array(pool.starmap(_one_cost_expl, jobs), dtype=np.float32)

            opt_expl = JADE(function=obj_batch_expl, lb=lb_expl, ub=ub_expl,
                            population_size=swarm_expl, max_evals=max_evals_expl,
                            initial_X=[], device='cpu')
            best_x_expl, _, _, _, _ = opt_expl.search()

            # After best_x_expl is found
            fmu_term, vr_term = make_fmu()
            fmu_term.setupExperiment(startTime=T0_snap)
            fmu_term.enterInitializationMode(); fmu_term.exitInitializationMode()
            # load_state(fmu_term, STATE0)
            
            
            try:
                load_state(fmu_term, STATE0)
            except FMICallException:
                print("[WARN] Restore failed. Retrying after fresh init...")
                fmu_term.freeInstance()
                fmu_term, vr_term = make_fmu()
                fmu_term.setupExperiment(startTime=T0, stopTime=TEND)
                fmu_term.enterInitializationMode(); fmu_term.exitInitializationMode()
                try:
                    load_state(fmu_term, STATE0)  # retry
                except FMICallException:
                    print("[WARN] Retry failed. Replaying past controls.")
                    t = 0.0
                    soc = fmu_term.getReal([vr_term['soc']])[0]
                    for pum_raw, pr_raw in past:
                        pum = 0.0 if pum_raw < 2.4 else pum_raw
                        pbat = projection(pr_raw, soc, STEPS_SECONDS)
                        fmu_term.setReal([vr_term['pumboi'], vr_term['pumhea'], vr_term['Pcharge']], [0.0, pum, pbat])
                        for _ in range(ITER_):
                            with redirect_stdout_stderr():
                                fmu_term.doStep(t, 60)
                            t += 60
                        soc = fmu_term.getReal([vr_term['soc']])[0]
            

            # NOTE: We'll only simulate the first day in low_res mode
            soc_term = fmu_term.getReal([vr_term['soc']])[0]
            steps_in_first_day = int((24 * 3600) / EXPL_STEP_SECONDS)  # number of low-res steps for 1 day

            u_term = np.column_stack((best_x_expl[:low_res_steps], best_x_expl[low_res_steps:]))

            t_local = T0_snap
            for (pum_raw, pr_raw) in u_term[:steps_in_first_day]:
                pum = 0.0 if pum_raw < 2.4 else pum_raw
                pbat = projection(pr_raw, soc_term, EXPL_STEP_SECONDS)
                fmu_term.setReal([vr_term['pumboi'], vr_term['pumhea'], vr_term['Pcharge']],
                                 [0.0, pum, pbat])
                for _ in range(int(EXPL_STEP_SECONDS / 60)):
                    with redirect_stdout_stderr():
                        fmu_term.doStep(t_local, 60)
                    t_local += 60
                soc_term = fmu_term.getReal([vr_term['soc']])[0]

            terminal_soc = soc_term
            fmu_term.freeInstance()
        else:
            terminal_soc = None

        # === LF (Middle resolution) optimization ===
        lb_LF = np.zeros(2 * (H // 2))
        ub_LF = np.zeros(2 * (H // 2))
        lb_LF[:H // 2] = 0; ub_LF[:H // 2] = 12.0
        lb_LF[H // 2:] = -1.0; ub_LF[H // 2:] = 1.0

        def _one_cost_LF(x, state, c0, t0, term_soc):
            try:
                u = np.column_stack((x[:H//2], x[H//2:]))
                return run_horizon(u, state, c0, t0, LF_STEP_SECONDS, term_soc)
            except FMICallException:
                return 1e6

        def obj_batch_LF(X_batch):
            state_copy_list = [copy.deepcopy(STATE0) for _ in range(len(X_batch))]
            with mp.Pool(processes=os.cpu_count()) as pool:
                jobs = [(x, state_copy_list[i], cost0, T0_snap, terminal_soc) for i, x in enumerate(X_batch)]
                return np.array(pool.starmap(_one_cost_LF, jobs), dtype=np.float32)

        opt_LF = JADE(function=obj_batch_LF, lb=lb_LF, ub=ub_LF,
                      population_size=swarm_LF, max_evals=max_evals_LF,
                      initial_X=[], device='cpu')
        best_x_LF, best_pop_LF, _, _, _ = opt_LF.search()

        def interpolate_to_HF(x_LF, factor=2):
            H_LF = len(x_LF) // 2
            pum_LF = x_LF[:H_LF]; pch_LF = x_LF[H_LF:]
            t_LF = np.arange(H_LF)
            t_HF = np.linspace(0, H_LF - 1, H_LF * factor)
            return np.concatenate([np.interp(t_HF, t_LF, pum_LF),
                                   np.interp(t_HF, t_LF, pch_LF)])

        lf_upscaled = np.array([interpolate_to_HF(ind) for ind in best_pop_LF])


        if elite_pool.size > 0:
            np.random.shuffle(elite_pool)  # randomize order
            num_elites = min(len(elite_pool), swarm_HF // 2)
            elites_to_use = elite_pool[:num_elites]
            num_from_lf = swarm_HF - num_elites
            lf_to_use = lf_upscaled[:num_from_lf]
            combined_init = np.vstack((elites_to_use, lf_to_use))
        else:
            combined_init = lf_upscaled[:swarm_HF]


        # === HF optimization ===
        lb_HF = np.zeros(2 * H)
        ub_HF = np.zeros(2 * H)
        lb_HF[:H] = 0; ub_HF[:H] = 12.0
        lb_HF[H:] = -1.0; ub_HF[H:] = 1.0

        def _one_cost_HF(x, state, c0, t0, term_soc):
            try:
                u = np.column_stack((x[:H], x[H:]))
                return run_horizon(u, state, c0, t0, STEPS_SECONDS, term_soc)
            except FMICallException:
                return 1e6

        def obj_batch_HF(X_batch):
            state_copy_list = [copy.deepcopy(STATE0) for _ in range(len(X_batch))]
            with mp.Pool(processes=os.cpu_count()) as pool:
                jobs = [(x, state_copy_list[i], cost0, T0_snap, terminal_soc) for i, x in enumerate(X_batch)]
                return np.array(pool.starmap(_one_cost_HF, jobs), dtype=np.float32)

        opt_HF = JADE(function=obj_batch_HF, lb=lb_HF, ub=ub_HF,
                      population_size=swarm_HF, max_evals=max_evals_HF,
                      initial_X=combined_init, device='cpu')
        best_x, best_pop, _, _, _ = opt_HF.search()


        if elite_warm_start and current_step >= BLOCK:
            if elite_pool.size == 0:
                elite_pool = best_pop.copy()
            else:
                elite_pool = np.vstack((elite_pool, best_pop))


        # Accept best design
        accepted = min(BLOCK, H)
        for k in range(accepted):
            pum = best_x[k]; pch = best_x[H + k]
            optimal_control.append([0.0 if pum < 2.4 else pum, pch])

        # Save result
        np.savetxt(os.path.join(run_results_dir, f"optimal_control_{current_step}.txt"), optimal_control)
        current_step += accepted
        print(f"[Run {run_id}] step {current_step:3d}/{total_steps - 1}")

        # Reset budgets after boosted cycle
        if max_evals_HF == max_evals_init_HF:
            max_evals_HF = max_evals_default_HF
        if max_evals_LF == max_evals_init_LF:
            max_evals_LF = max_evals_default_LF
        if max_evals_expl == max_evals_init_expl:
            max_evals_expl = max_evals_default_expl

    optimal_control_array = np.vstack(optimal_control)
    np.save(os.path.join(run_results_dir, "optimal_control.npy"), optimal_control_array)
    print(f"Finished run {run_id}. optimal_control.shape = {optimal_control_array.shape}")

