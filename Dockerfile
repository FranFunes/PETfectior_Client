FROM python:3.11

WORKDIR /home/petfectior

COPY requirements.txt requirements.txt
RUN python -m venv envPETfectiorClient
RUN envPETfectiorClient/bin/pip install --upgrade pip
RUN envPETfectiorClient/bin/pip install -r requirements.txt
RUN envPETfectiorClient/bin/pip install gunicorn

RUN apt-get -y update
RUN apt-get install -y bridge-utils cifs-utils openvpn iputils-ping dos2unix iproute2 net-tools traceroute
RUN mkdir shared

COPY app_pkg app_pkg
COPY migrations migrations
COPY petfectior_client.py config.py boot.sh init_db.py ./
RUN dos2unix < boot.sh > boot_bkp.sh
RUN rm boot.sh
RUN mv boot_bkp.sh boot.sh
RUN chmod +x boot.sh

EXPOSE 8000
EXPOSE 11115

CMD ["./boot.sh"]