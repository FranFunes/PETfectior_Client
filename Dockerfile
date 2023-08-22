FROM python:3

WORKDIR /home/petfectior

COPY requirements.txt requirements.txt
RUN python -m venv envPETfectiorClient
RUN envPETfectiorClient/bin/pip install --upgrade pip
RUN envPETfectiorClient/bin/pip install -r requirements.txt

RUN apt-get -y update
RUN apt-get install -y bridge-utils cifs-utils openvpn iputils-ping dos2unix iproute2 net-tools traceroute
RUN mkdir shared

COPY app_pkg app_pkg
COPY migrations migrations
COPY client_side_app.py config.py start.sh ./
RUN dos2unix < start.sh > start_bkp.sh
RUN rm start.sh
RUN mv start_bkp.sh start.sh
RUN chmod +x start.sh

EXPOSE 8000
EXPOSE 11115

CMD ["./start.sh"]