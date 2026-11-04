import math
import statistics


def validate_measurement(data, sha):
    if data.get('schema') != 1 or data.get('sha') != sha:
        raise ValueError('Benchmark schema or commit does not match.')
    if data.get('name') != 'julia_linear_solve_512' or data.get('unit') != 'seconds':
        raise ValueError('Unexpected benchmark or unit.')
    for key in ('value', 'residual'):
        if type(data[key]) not in (int, float) or not math.isfinite(data[key]):
            raise ValueError(f'Invalid {key}.')
    samples = data['samples']
    if not isinstance(samples, list) or len(samples) != 7:
        raise ValueError('Expected seven timing samples.')
    if any(type(value) not in (int, float) or not math.isfinite(value) or value <= 0 for value in samples):
        raise ValueError('Invalid timing sample.')
    if not math.isclose(data['value'], statistics.median(samples), rel_tol=1e-12):
        raise ValueError('The reported median does not match the samples.')
    if not 0 <= data['residual'] < 1e-12 or data.get('threads') != 1 or data.get('blas_threads') != 1:
        raise ValueError('The solve or thread configuration is invalid.')
    for key in ('cpu', 'blas', 'julia_version'):
        if not isinstance(data[key], str) or not 0 < len(data[key]) <= 1000:
            raise ValueError(f'Invalid {key} metadata.')
    return data

