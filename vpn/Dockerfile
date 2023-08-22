FROM ubuntu:latest

RUN apt-get -y update
RUN apt-get -y install openvpn dos2unix

COPY start.sh start.sh
RUN dos2unix < start.sh > start_bkp.sh
RUN rm start.sh
RUN mv start_bkp.sh start.sh
RUN chmod +x start.sh

CMD ["./start.sh"]