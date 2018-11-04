import numpy as np
from sklearn.base import BaseEstimator, RegressorMixin, ClassifierMixin
from sklearn.metrics import log_loss, mean_squared_error
import pandas as pd

from .util import sigmoid, add_intercept


def _prox(coef, thresh, group_ids):
    """
    Proximal operator.
    Group sparsity case: apply group sparsity operator
    """
    df = pd.DataFrame({
        "group_id": group_ids,
        "coef": coef
    })
    lst = []
    for group_id, v in df.groupby("group_id"):
        group_norm = np.linalg.norm(v['coef'], 2)
        multiplier = max(0, 1 - thresh / group_norm)
        lst.append([group_id, multiplier])

    group_norms = pd.DataFrame(lst).rename(
        columns={0: "group_id", 1: "multiplier"}
    )
    out = df.merge(group_norms, how='left')
    return (out['multiplier'] * out['coef']).values


class GroupLassoRegressor(BaseEstimator, RegressorMixin):
    def __init__(self, group_ids, random_state=None,
                 alpha=1e-3, eta=1e-1,
                 tol=1e-4, max_iter=1000,
                 verbose=True, verbose_interval=1):
        self.group_ids = group_ids
        self.random_state = random_state
        self._rng = np.random.RandomState(random_state)
        self.alpha = alpha
        self.eta = eta
        self.tol = tol
        self.max_iter = max_iter
        self.verbose = verbose
        self.verbose_interval = verbose_interval

    def fit(self, X, y):
        n_samples = len(X)
        X = add_intercept(X)
        n_features = X.shape[1]
        w = self._rng.randn(n_features)
        thresh = self.eta * self.alpha
        for itr in range(self.max_iter):
            w_old = w.copy()
            pred = X @ w
            if self.verbose and itr % self.verbose_interval == 0:
                loss = mean_squared_error(y, pred)
                print("training loss:", loss)

            diff = 1 / n_samples * X.T @ (pred - y)
            out = w - self.eta * diff

            w[:-1] = _prox(out[:-1], thresh, self.group_ids)
            w[-1] = out[-1]
            if np.linalg.norm(w_old - w, 2) ** 2 < self.tol:
                if self.verbose:
                    print("Converged. itr={}".format(itr))
                break

        self.coef_ = w[:-1]
        self.intercept_ = w[-1]
        self.n_iter_ = itr

    def predict(self, X):
        return X @ self.coef_ + self.intercept_


class GroupLassoClassifier(BaseEstimator, ClassifierMixin):
    def __init__(self, group_ids, random_state=None,
                 alpha=1e-3, eta=1e-1,
                 tol=1e-4, max_iter=1000,
                 verbose=True, verbose_interval=1):
        self.group_ids = group_ids
        self.random_state = random_state
        self._rng = np.random.RandomState(random_state)
        self.alpha = alpha
        self.eta = eta
        self.tol = tol
        self.max_iter = max_iter
        self.verbose = verbose
        self.verbose_interval = verbose_interval

    def fit(self, X, y):
        if isinstance(X, pd.DataFrame):
            X = X.values

        if isinstance(y, pd.Series):
            y = y.values

        # binary classification
        assert ((y == 0) | (y == 1)).all()

        n_samples = len(X)
        X = add_intercept(X)
        n_features = X.shape[1]
        w = self._rng.randn(n_features)
        thresh = self.eta * self.alpha
        for itr in range(self.max_iter):
            w_old = w.copy()
            proba = sigmoid(X @ w)
            if self.verbose and itr % self.verbose_interval == 0:
                loss = log_loss(y, proba)
                print("training loss:", loss)

            diff = 1 / n_samples * X.T @ (proba - y)
            out = w - self.eta * diff

            w[:-1] = _prox(out[:-1], thresh, self.group_ids)
            w[-1] = out[-1]
            if np.linalg.norm(w_old - w, 2) ** 2 < self.tol:
                if self.verbose:
                    print("Converged. itr={}".format(itr))
                break

        self.coef_ = w[:-1]
        self.intercept_ = w[-1]
        self.n_iter_ = itr

    def predict_proba(self, X):
        proba = np.zeros((len(X), 2), dtype=np.float64)
        score = X @ self.coef_ + self.intercept_
        proba[:, 1] = sigmoid(score)
        proba[:, 0] = 1 - proba[:, 1]
        return proba

    def predict(self, X):
        proba = self.predict_proba(X)
        return (proba[:, 1] > 0.5).astype(int)
