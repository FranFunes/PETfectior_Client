FROM python:3

RUN useradd petfectior

WORKDIR /home/petfectior

COPY requirements.txt requirements.txt
RUN python -m venv envPETfectiorClient
RUN envPETfectiorClient/bin/pip install --upgrade pip
RUN envPETfectiorClient/bin/pip install -r requirements.txt

RUN apt-get -y update
RUN apt-get install -y bridge-utils cifs-utils
RUN mkdir shared

COPY app_pkg app_pkg
COPY migrations migrations
COPY client_side_app.py config.py start.sh ./
RUN chmod +x start.sh
RUN chown -R petfectior:petfectior ./

EXPOSE 8000
EXPOSE 11115

CMD ["./start.sh"]