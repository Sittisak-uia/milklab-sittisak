FROM python:3.11-slim

WORKDIR /app

# Set environment variables to limit PyTorch/OpenBLAS thread allocations (keeps memory under 512MB)
ENV OMP_NUM_THREADS=1
ENV MKL_NUM_THREADS=1
ENV OPENBLAS_NUM_THREADS=1
ENV VECLIB_MAXIMUM_THREADS=1
ENV NUMEXPR_NUM_THREADS=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .

# Install CPU-only torch to save 2GB+ of disk space and reduce memory overhead, then install other packages
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

CMD streamlit run app.py --server.port=$PORT --server.address=0.0.0.0