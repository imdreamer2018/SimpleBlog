FROM python:3.6

WORKDIR /app

COPY ./app/requirements/common.txt /app/requirements.txt
RUN mkdir ~/.pip && \
    cd ~/.pip/  && \
    echo "[global] \ntrusted-host =  mirrors.aliyun.com \nindex-url = http://mirrors.aliyun.com/pypi/simple" >  pip.conf
RUN pip install --default-timeout=1000 --no-cache-dir -r requirements.txt

COPY ./ /app

CMD ["gunicorn", "main:app", "-c", "./gunicorn.conf.py"]
