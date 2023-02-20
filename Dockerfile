FROM python:3.11-alpine
WORKDIR /usr/src/myapp
COPY bowtie_jsch.py .
COPY classes.py .
COPY schema.py .
COPY utils.py .
CMD ["python3", "bowtie_jsch.py"]
