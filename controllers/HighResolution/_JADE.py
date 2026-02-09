import numpy as np
import matplotlib.pyplot as plt
import sys
import time
import torch




class JADE:
    
    def __init__(self, function, lb, ub, population_size, max_evals, 
                 p=0.05, c=0.1, initial_X=[],  device='cpu'):
        
        self.function = function
        self.lb = lb
        self.ub = ub
        self.population_size = population_size
        self.max_evals = max_evals
        self.p = p
        self.c = c
        self.initial_X = initial_X
        self.device = device
        
        if self.device == 'cuda':
            
            self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

        else:
            self.device = torch.device('cpu')
        
        self.dtype = torch.float32
                
        self.lower = torch.as_tensor(self.lb, device=self.device, dtype=self.dtype)
        self.upper = torch.as_tensor(self.ub, device=self.device, dtype=self.dtype)
        self.initial_X = torch.as_tensor(self.initial_X, device=self.device, dtype=self.dtype)
        self.D = self.lower.shape[0]
        
        self.mu_cr = 0.5
        self.mu_f = 0.5
        
        
        """checks"""
        
        if self.lb.shape != self.ub.shape:
            raise ValueError("Lower and upper boundaries are not the same shape!")
            
        if self.initial_X.shape[0] > self.population_size:
            raise ValueError("Initial design vector is larger than the population size!")
            
    def _evaluate(self, X):
        
        f = torch.as_tensor(self.function(X.cpu().numpy()), device=self.device, dtype=self.dtype)       
        
        return f.unsqueeze(1)

    def _initialize(self):
        
        if len(self.initial_X) == 0:
            
            X = torch.rand((self.population_size, *self.lower.shape), device=self.device, dtype=self.dtype) * (self.upper - self.lower) + self.lower
                   
        else:
            
            X = torch.clamp(self.initial_X, min=self.lower, max=self.upper)
            
            if X.shape[0] < self.population_size:
                X = torch.vstack((X, torch.rand((self.population_size-X.shape[0], *self.lower.shape), \
                                               device=self.device, dtype=self.dtype) * (self.upper - self.lower) + self.lower))            
        
        return X
    
    @torch.no_grad() 
    def _crossover(self, X, V, Cr):
        
        mask = torch.rand(self.population_size, self.D, device=self.device) < Cr
        j_rand = torch.randint(0, self.D, (self.population_size, 1), device=self.device)      
        mask.scatter_(1, j_rand, True)       
        U = torch.where(mask, V, X)  
        
        return U
        
        
    
    @torch.no_grad() 
    def _mutate_crossover(self, X, elite, A, Cr, F):
        
        # """jade current-to-pbest/1/bin"""

        p_len  = elite.size(0)
        eye = torch.arange(self.population_size, device=self.device)
    
        rpbest = elite[torch.randint(p_len, (self.population_size,), device=self.device)]
        same = rpbest == eye
        while same.any():                                     # very few hits
            rpbest[same] = elite[torch.randint(p_len,
                                               (same.sum(),), device=self.device)]
            same = rpbest == eye
        
        mask_pop = torch.ones((self.population_size, self.population_size), dtype=torch.bool, device=self.device)
        mask_pop[eye, eye] = False
        mask_pop[eye, rpbest] = False
        r1 = torch.multinomial(mask_pop.float(), 1).squeeze(1)
        
        union = torch.cat((X, A), dim=0)
        N_union = self.population_size + A.size()[0]
    
        mask_all = torch.ones((self.population_size, N_union), dtype=torch.bool, device=self.device)
        mask_all[eye, eye]   = False
        mask_all[eye, rpbest] = False
        mask_all[eye, r1] = False
        r2 = torch.multinomial(mask_all.float(), 1).squeeze(1)    
    
        V = X + F * (X[rpbest] - X + X[r1] - union[r2])

        U = self._crossover(X, V, Cr)
        
        U = torch.maximum(U, self.lower)
        U = torch.minimum(U, self.upper)
            
        return U
    
    def _archive(self, A, A_):
        
        if A.numel() == 0:      
            A = A_
        else:
            
            if A.size()[0]  >= self.population_size:               
                k = A_.size(0)
                rnd_indx = torch.randperm(A.size(0), device=self.device)[:k]
                A[rnd_indx] = A_
           
            else:
                A = torch.cat((A, A_), 0)
                
        return A
    
    def _adapt(self, Scr=None, Sf=None, w=None):
        
        if Scr is not None and Scr.numel() > 0:            
                      
            self.mu_cr = (1 - self.c) * self.mu_cr + self.c * (Scr.squeeze(1) * w).sum()

            self.mu_f  = (1 - self.c) * self.mu_f  + self.c * (Sf.square().sum() /
                                                   Sf.sum())

        Cr = torch.clamp(torch.distributions.Normal(self.mu_cr, 0.1).sample((self.population_size, 1)), 0.05, 1).to(self.device)
        F = torch.clamp(torch.distributions.Cauchy(self.mu_f, 0.1).sample((self.population_size, 1)), 0.4, 1).to(self.device)

        return Cr, F
        

    @torch.no_grad() 
    def search(self):
        
        X = self._initialize()
        fX = self._evaluate(X)
        A = torch.empty((0, self.D), device=self.device, dtype=self.dtype)
        
        Cr, F = self._adapt()
                 
        evals = fX.shape[0]
        while evals < self.max_evals - fX.shape[0]:

            p = max(2, int(fX.shape[0]*self.p))
            elite = torch.argsort(fX.T)[0][:p]
  
            U = self._mutate_crossover(X, elite, A, Cr, F)
            fU = self._evaluate(U)
            evals = evals + fU.size()[0]

            mask_adapt = fU < fX               
            if mask_adapt.any().item():

                """archive"""
                A_ = X[torch.where(mask_adapt==False)[0]].clone()
                A = self._archive(A, A_)
               
                """param update"""
                deltaF = torch.abs(fU - fX)
                w = deltaF[mask_adapt]/torch.sum(deltaF[mask_adapt])
                Scr = Cr[mask_adapt.squeeze(1)]
                Sf = F[mask_adapt.squeeze(1)]    
                Cr, F = self._adapt(Scr, Sf, w)

            mask = fU <= fX               
            X = torch.where(mask, U, X) 
            fX = torch.where(mask, fU, fX)
            
            print ('Evals:', evals, '->', 'Best solution fitness:', fX[torch.argmin(fX).item()].item())

        f_best_indx = torch.argmin(fX).item()


        return X[f_best_indx].cpu().numpy(), X.cpu().numpy(), fX[f_best_indx].cpu().numpy()

        

