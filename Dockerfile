FROM python:3.9-slim as base

# Setup env
ENV LANG C.UTF-8
ENV LC_ALL C.UTF-8
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONFAULTHANDLER 1


FROM base AS python-deps

# Install pipenv and compilation dependencies
RUN apt update && apt upgrade -y && apt install -y gcc

# Install python dependencies in /.venv
COPY requirements.txt .
RUN python3 -m venv /.venv
RUN /.venv/bin/pip install -Ur requirements.txt


FROM base AS runtime

# Copy virtual env from python-deps stage
COPY --from=python-deps /.venv /.venv
ENV PATH="/.venv/bin:$PATH"

# Create and switch to a new user
RUN useradd --create-home appuser
WORKDIR /home/appuser


# Install application into container
COPY main.py .
RUN chown appuser /home/appuser/main.py

USER appuser

# Run the application
ENTRYPOINT ["python", "main.py"]