FROM python:3
ADD . /apocrypha/
RUN pip --disable-pip-version-check install /apocrypha
VOLUME ["/tmp/dbs"]
CMD ["python3", "-m", "apocrypha.node"]

# RUN pip install --upgrade pip https://github.com/Gandalf-/apocrypha/archive/node.zip
# EXPOSE 9999/tcp
