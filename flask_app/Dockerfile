FROM python:3.10

COPY requirements.txt requirements.txt
COPY dandihera-key.json dandihera-key.json
RUN pip install -r requirements.txt

COPY . /app

WORKDIR /app

CMD ["flask", "run", "--host=0.0.0.0"]

