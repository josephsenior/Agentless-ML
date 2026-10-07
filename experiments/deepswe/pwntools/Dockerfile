# Diagnostic environment only: never replace the published DeepSWE image.
FROM agentless-ml/pwntools-base:8d726c8e36df

COPY requirements.txt /opt/pwntools-docs-requirements.txt

# Public docs/requirements.txt requests Sphinx >=8.1.3,<9 and autoprogram <=0.1.5.
# Keep the image's existing runtime dependencies visible and unchanged.
RUN python -m pip list --format=json > /opt/pwntools-base-packages.json \
    && python -m venv --system-site-packages /opt/pwntools-docs \
    && /opt/pwntools-docs/bin/python -m pip install --no-cache-dir \
       --report /opt/pwntools-docs-install.json -r /opt/pwntools-docs-requirements.txt \
    && /opt/pwntools-docs/bin/python -m pip list --format=json > /opt/pwntools-docs-packages.json \
    && /opt/pwntools-docs/bin/python -m pip check

ENV PATH="/opt/pwntools-docs/bin:${PATH}"
