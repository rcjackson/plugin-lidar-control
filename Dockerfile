FROM waggle/plugin-base:1.1.1-ml-torch1.9

RUN apt-get update -y
RUN apt-get install -y python3-tk
#RUN apt-get install -y libhdf5-serial-dev

RUN pip3 install scipy==1.4.1
#RUN pip3 uninstall -y tensorflow
RUN pip3 install --pre --extra-index-url https://developer.download.nvidia.com/compute/redist/jp/v44 tensorflow==2.3.0+nv20.9
RUN pip3 install netcdf4
RUN pip3 install xarray
RUN pip3 install matplotlib
#RUN pip3 install --upgrade keras-preprocessing
RUN pip3 install --upgrade pywaggle
RUN pip3 install act-atmos==1.1.0
#RUN pip3 install --upgrade xarray

ENV MPLBACKEND="agg"

COPY app/ /app/
COPY app/*.json /app/
COPY app/*.hdf5 /app/
COPY *.home_point /app/
COPY data /data/
COPY data/* /data/
ADD https://anl.box.com/shared/static/lmc19q9mj6rir8j8ecz3765dee30xvmo.hdf5 /app/resnet50.hdf5
ADD https://anl.box.com/shared/static/u3zp2bt1851x8p2wjybc7wfipirodv76.hpl /data/Stare_240_20230324_15.hpl
WORKDIR /app

ENTRYPOINT ["python3", "/app/app.py"]

