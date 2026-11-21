"""Projeção de um stem vocal estéreo sobre a sua imagem coerente dominante."""

import numpy as np


def vocal_axis(stereo: np.ndarray) -> tuple[float, float]:
    """Eixo unitário L/R. O eixo Mid serve de referência nas misturas difusas.

    Uma voz muito panoramizada ou com um canal invertido exige outra projeção.
    O eixo é fixo na faixa para evitar saltos de polaridade entre frases.
    """
    mid_axis = (2**-.5, 2**-.5)
    if stereo.ndim != 2 or stereo.shape[1] != 2 or not len(stereo):
        return mid_axis
    covariance = np.einsum("ni,nj->ij", stereo, stereo, dtype="d")
    left, right = covariance.diagonal()
    power = left + right
    if power < 1e-12:
        return mid_axis
    coherence = covariance[0, 1]/max(np.sqrt(left*right), 1e-12)
    unbalanced = min(left, right) < .25*max(left, right)
    if coherence >= -.70 and not unbalanced:
        return mid_axis
    values, axes = np.linalg.eigh(covariance)
    if values[-1] < .90*power:
        return mid_axis
    axis = axes[:, -1]
    # Mesma referência de polaridade durante a separação e a renderização.
    dominant = 1 if right > 1.01*left else 0
    if axis[dominant] < 0:
        axis = -axis
    return float(axis[0]), float(axis[1])
