# Online training of a logistic regression model
# using Assumed Density Filtering (ADF).
# We compare the ADF result with MCMC sampling
# For further details, see the ADF paper:
#   * O. Zoeter, "Bayesian Generalized Linear Models in a Terabyte World,"
#     2007 5th International Symposium on Image and Signal Processing and Analysis, 2007,
#     pp. 435-440, doi: 10.1109/ISPA.2007.4383733.
# of the posterior distribution
# Dependencies:
#   !pip install jax_cosmo

# Author: Gerardo Durán-Martín (@gerdm)

import superimport

import jax
import jax.numpy as jnp
import matplotlib.pyplot as plt
import pyprobml_utils as pml
from jax import random
from jax.scipy.stats import norm
from jax_cosmo.scipy import integrate
from functools import partial
from jsl.demos import logreg_biclusters_demo as demo

import pyprobml_utils as pml

# cosmo seems to only support numerical integration in CPU mode
jax.config.update("jax_platform_name", "cpu")
jax.config.update("jax_enable_x64", True)

figures, data = demo.main()

X = data["X"]
y = data["y"]
Phi = data["Phi"]
Xspace = data["Xspace"]
Phispace = data["Phispace"]
w_laplace = data["w_laplace"]

def sigmoid(z): return jnp.exp(z) / (1 + jnp.exp(z))
def log_sigmoid(z): return z - jnp.log1p(jnp.exp(z))

def Zt_func(eta, y, mu, v):
    log_term = y * log_sigmoid(eta) + (1 - y) * jnp.log1p(-sigmoid(eta))
    log_term = log_term + norm.logpdf(eta, mu, v)
    
    return jnp.exp(log_term)


def mt_func(eta, y, mu, v, Zt):
    log_term = y * log_sigmoid(eta) + (1 - y) * jnp.log1p(-sigmoid(eta))
    log_term = log_term + norm.logpdf(eta, mu, v)
    
    return eta * jnp.exp(log_term) / Zt


def vt_func(eta, y, mu, v, Zt):
    log_term = y * log_sigmoid(eta) + (1 - y) * jnp.log1p(-sigmoid(eta))
    log_term = log_term + norm.logpdf(eta, mu, v)
    
    return eta ** 2 * jnp.exp(log_term) / Zt


def adf_step(state, xs, prior_variance, lbound, ubound):
    mu_t, tau_t = state
    Phi_t, y_t = xs
    
    mu_t_cond = mu_t
    tau_t_cond = tau_t + prior_variance

    # prior predictive distribution
    m_t_cond = (Phi_t * mu_t_cond).sum()
    v_t_cond = (Phi_t ** 2 * tau_t_cond).sum()

    v_t_cond_sqrt = jnp.sqrt(v_t_cond)

    # Moment-matched Gaussian approximation elements
    Zt = integrate.romb(lambda eta: Zt_func(eta, y_t, m_t_cond, v_t_cond_sqrt), lbound, ubound)

    mt = integrate.romb(lambda eta: mt_func(eta, y_t, m_t_cond, v_t_cond_sqrt, Zt), lbound, ubound)

    vt = integrate.romb(lambda eta: vt_func(eta, y_t, m_t_cond, v_t_cond_sqrt, Zt), lbound, ubound)
    vt = vt - mt ** 2
    
    # Posterior estimation
    delta_m = mt - m_t_cond
    delta_v = vt - v_t_cond
    a = Phi_t * tau_t_cond / (Phi_t ** 2 * tau_t_cond).sum()
    mu_t = mu_t_cond + a * delta_m
    tau_t = tau_t_cond + a ** 2 * delta_v
    
    return (mu_t, tau_t), (mu_t, tau_t)

# ** ADF inference **
prior_variance = 0.0
# Lower and upper bounds of integration. Ideally, we would like to
# integrate from -inf to inf, but we run into numerical issues.
n_datapoints, ndims = Phi.shape
lbound, ubound = -20, 20
mu_t = jnp.zeros(ndims)
tau_t = jnp.ones(ndims) * 1.0

init_state = (mu_t, tau_t)
xs = (Phi, y)

adf_loop = partial(adf_step, prior_variance=prior_variance, lbound=lbound, ubound=ubound)
(mu_t, tau_t), (mu_t_hist, tau_t_hist) = jax.lax.scan(adf_loop, init_state, xs)
print("ADF weights")
print(mu_t)

# ADF posterior predictive distribution
n_samples = 5000
key = random.PRNGKey(3141)
adf_samples = random.multivariate_normal(key, mu_t, jnp.diag(tau_t), (n_samples,))
Z_adf = sigmoid(jnp.einsum("mij,sm->sij", Phispace, adf_samples))
Z_adf = Z_adf.mean(axis=0)

# ** Plotting predictive distribution **
colors = ["black" if el else "white" for el in y]

## Add posterior marginal for ADF-estimated weights
for i in range(ndims):
    mean, std = mu_t[i], jnp.sqrt(tau_t[i])
    #fig = figures[f"weights_marginals_w{i}"]
    fig = figures[f"logistic_regression_weights_marginals_w{i}"]
    ax = fig.gca()
    x = jnp.linspace(mean - 4 * std, mean + 4 * std, 500)
    ax.plot(x, norm.pdf(x, mean, std), label="posterior (ADF)", linestyle="dashdot")
    ax.legend()

fig_adf, ax = plt.subplots()
title = "ADF Predictive distribution"
demo.plot_posterior_predictive(ax, X, Xspace, Z_adf, title, colors)
#figures["predictive_distribution_adf"] = fig_adf
#figures["logistic_regression_surface_adf"] = fig_adf
pml.savefig("logistic_regression_surface_adf.pdf")

# Posterior vs time

lcolors = ["black", "tab:blue", "tab:red"]
elements = mu_t_hist.T, tau_t_hist.T, w_laplace, lcolors
timesteps = jnp.arange(n_datapoints) + 1

for k, (wk, Pk, wk_laplace, c) in enumerate(zip(*elements)):
    fig_weight_k, ax = plt.subplots()
    ax.errorbar(timesteps, wk, jnp.sqrt(Pk), c=c, label=f"$w_{k}$ online (adf)")
    ax.axhline(y=wk_laplace, c=c, linestyle="dotted", label=f"$w_{k}$ batch (Laplace)", linewidth=3)

    ax.set_xlim(1, n_datapoints)
    ax.legend(framealpha=0.7, loc="upper right")
    ax.set_xlabel("number samples")
    ax.set_ylabel("weights")
    plt.tight_layout()
    #figures[f"adf_logistic_regression_hist_w{k}"] = fig_weight_k
    #figures[f"logistic_regression_hist_adf_w{k}"] = fig_weight_k
    pml.savefig(f"logistic_regression_hist_adf_w{k}")

#for name, figure in figures.items():
#    filename = f"./../figures/{name}.pdf"
#    figure.savefig(filename)

plt.show()
