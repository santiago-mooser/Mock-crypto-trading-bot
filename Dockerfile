FROM pypy:3.10-7.3.16-slim
# FROM python:3.12-slim

RUN apt-get update && apt-get -yqq install gcc clang llvm build-essential
RUN python -m ensurepip
RUN python -m pip install -U pip wheel setuptools --upgrade

# install dependencies
COPY requirements.txt /tmp/requirements.txt
RUN python -m pip install --no-cache-dir -r /tmp/requirements.txt

# copy the source code
COPY . /app
WORKDIR /app

# run the application
CMD ["pypy", "median_liquidity_trader.py"]

# CMD "python", "-m", "cProfile", "-o", "/data/median_liquidity_trader.prof", "median_liquidity_trader.py"]