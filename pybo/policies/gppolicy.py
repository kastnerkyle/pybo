"""
Wrapper class for simple GP-based policies whose acquisition functions are
simple functions of the posterior sufficient statistics.
"""

# future imports
from __future__ import division
from __future__ import absolute_import
from __future__ import print_function

# global imports
import numpy as np

# not "exactly" local, but...
import pygp
import pygp.meta

# local imports
from ._base import Policy
from .. import globalopt
from . import acquisitions

# exported symbols
__all__ = ['GPPolicy']


### ENUMERATE POSSIBLE META POLICY COMPONENTS #################################

def _make_dict(module, lstrip='', rstrip=''):
    """
    Given a module return a dictionary mapping the name of each of its exported
    functions to the function itself.
    """
    def generator():
        """Generate the (name, function) tuples."""
        for fname in module.__all__:
            f = getattr(module, fname)
            if fname.startswith(lstrip):
                fname = fname[len(lstrip):]
            if fname.endswith(rstrip):
                fname = fname[::-1][len(rstrip):][::-1]
            fname = fname.lower()
            yield fname, f
    return dict(generator())

MODELS = _make_dict(pygp.meta)
SOLVERS = _make_dict(globalopt, lstrip='solve_')
POLICIES = _make_dict(acquisitions)


#### DEFINE THE META POLICY ###################################################

class GPPolicy(Policy):
    """
    Meta-policy for GP-based Bayesian optimization.
    """
    def __init__(self, bounds, noise,
                 kernel='matern3',
                 solver='lbfgs',
                 policy='ei',
                 inference='fixed',
                 prior=None):

        # make sure the bounds are a 2d-array.
        bounds = np.array(bounds, dtype=float, ndmin=2)

        if isinstance(kernel, str):
            # FIXME: come up with some sane initial hyperparameters.
            sn = noise
            sf = 1.0
            ell = (bounds[:, 1] - bounds[:, 0]) / 10
            gp = pygp.BasicGP(sn, sf, ell, kernel=kernel)

            if prior is None:
                # FIXME: this is not necessarily a good default prior, but it's
                # useful for testing purposes for now.
                prior = dict(
                    sn=pygp.priors.Uniform(0.01, 1.0),
                    sf=pygp.priors.Uniform(0.01, 5.0),
                    ell=pygp.priors.Uniform([0.01]*len(ell), 2*ell))

        else:
            gp = pygp.inference.ExactGP(pygp.likelihoods.Gaussian(noise),
                                        kernel)

        if inference is not 'fixed' and prior is None:
            raise Exception('a prior must be specified for models with'
                            'hyperparameter inference and non-default kernels')

        # save all the bits of our meta-policy.
        self._bounds = bounds
        self._solver = SOLVERS[solver]
        self._policy = POLICIES[policy]

        if inference is 'fixed':
            self._model = gp
        else:
            self._model = MODELS[inference](gp, prior, n=10)

        # FIXME: this is assuming that the inference methods all correspond to
        # Monte Carlo estimators where the number of samples can be selected by
        # a kwarg n. We probably want to have a default here for those type of
        # models, but should allow this to be changed (probably via kwargs in
        # GPPolicy).

    def add_data(self, x, y):
        self._model.add_data(x, y)

    def get_init(self):
        lo = self._bounds[:, 0]
        wd = self._bounds[:, 1] - lo

        # this basic example just returns a single point centered at the middle
        # of the bounded region.
        init = lo + 0.5 * wd
        return init[None]

    def get_next(self, return_index=False):
        # pylint: disable=arguments-differ
        index = self._policy(self._model)
        xnext, _ = self._solver(index, self._bounds, maximize=True)
        return (xnext, index) if return_index else xnext

    def get_best(self):
        def objective(X, grad=False):
            """Objective corresponding to the posterior mean."""
            if grad:
                return self._model.posterior(X, True)[::2]
            else:
                return self._model.posterior(X)[0]
        Xtest, _ = self._model.data
        xbest, _ = globalopt.solve_lbfgs(objective, self._bounds, xx=Xtest,
                                         maximize=True)
        return xbest