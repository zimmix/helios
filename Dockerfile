FROM python:3.9

#ENV TZ="America/Los_Angeles"

# set a directory for the app
WORKDIR /usr/src/evscc

# copy all the files to the container
COPY src/ .
COPY requirements.txt .

# install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# run the command
CMD ["python", "./helios"]
