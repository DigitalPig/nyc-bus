FROM continuumio/miniconda3

# COPY necessary files inside
ADD ./templates /opt/web/templates
WORKDIR /opt/web
COPY environment.yml /opt/web
COPY wsgi.py /opt/web
COPY app.py /opt/web
COPY config.py /opt/web
COPY start.sh /opt/web

RUN conda update -y conda && \
    conda env create -f environment.yml

CMD bash ./start.sh