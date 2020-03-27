FROM container-aria-jpl_ariamh:python3

MAINTAINER jlinick "Justin.P.Linick@jpl.nasa.gov"
LABEL description="GRFN PGE container for COD product generation"

ARG id
ARG gid

# create work directory
RUN set -ex \
    && mkdir -p /data/work \
    && chmod -R 755 /data \
    && chown -R ops:ops /data

USER root

#install shapely
RUN source /home/ops/verdi/bin/activate \ 
    && pip install shapely

# copy code ensure proper permissions, and move dependencies to final locations
COPY . /home/ops/verdi/ops/slcp2cod
RUN set -ex \
    && sudo chown -R ops:ops /home/ops/verdi/ops/slcp2cod \
    && cd /home/ops/verdi/ops/slcp2cod/src \
    && ./compile.sh

# set entrypoint
USER ops
WORKDIR /home/ops
CMD ["/bin/bash", "--login"]

