"""
Local gradient-based solver using multiple restarts.
"""

# future imports
from __future__ import division
from __future__ import absolute_import
from __future__ import print_function

# global imports
import numpy as np
import scipy.optimize

# local imports
from ...utils import ldsample

# exported symbols
__all__ = ['solve_lbfgs']


def solve_lbfgs(f,
                bounds,
                nbest=10,
                ninit=10000,
                xinit=None,
                rng=None):
    """
    Compute the objective function on an initial grid, pick `nbest` points, and
    maximize using LBFGS from these initial points.

    Args:
        f: function handle that takes an optional `grad` boolean kwarg
           and if `grad=True` returns a tuple of `(function, gradient)`.
           NOTE: this functions is assumed to allow for multiple inputs in
           vectorized form.

        bounds: bounds of the search space.
        nbest: number of best points from the initial test points to refine.
        ninit: number of (random) grid points to test initially.
        xinit: initial test points; ninit is ignored if this is given.

    Returns:
        xmin, fmax: location and value of the maximizer.
    """

    if xinit is None:
        # TODO: The following line could be replaced with a regular grid or a
        # Sobol grid.
        xinit = ldsample.random(bounds, ninit, rng)

    # compute func_grad on points xinit
    finit = f(xinit, grad=False)
    idx_sorted = np.argsort(finit)[::-1]

    # lbfgsb needs the gradient to be "contiguous", squeezing the gradient
    # protects against func_grads that return ndmin=2 arrays. We also need to
    # negate everything so that we are maximizing.
    def objective(x):
        fx, gx = f(x[None], grad=True)
        return -fx[0], -gx[0]

    # TODO: the following can easily be multiprocessed
    result = [scipy.optimize.fmin_l_bfgs_b(objective, x0, bounds=bounds)[:2]
              for x0 in xinit[idx_sorted[:nbest]]]

    # loop through the results and pick out the smallest.
    xmin, fmin = result[np.argmin(_[1] for _ in result)]

    # return the values (negate if we're finding a max)
    return xmin, -fmin
