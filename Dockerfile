FROM python:3

RUN apt-get -y update
RUN apt-get install -y bridge-utils cifs-utils
RUN mkdir /mnt/nas


COPY requirements.txt requirements.txt
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

WORKDIR /code

COPY app_pkg app_pkg
COPY services services
COPY client_side_app.py client_side_app.py
COPY init_services.py init_services.py

EXPOSE 8000

COPY start.sh /
RUN chmod +x /start.sh

CMD ["/start.sh"]