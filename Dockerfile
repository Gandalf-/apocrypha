FROM python:3
RUN pip install --upgrade pip https://github.com/Gandalf-/apocrypha/archive/node.zip
EXPOSE 9999/tcp
CMD ["python3", "-m", "apocrypha.node"]
