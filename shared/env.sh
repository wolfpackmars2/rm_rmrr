#!/bin/sh -
if ! [ "$(id -u)" -eq 0 ]; then
    echo "Must be root"
    exit 1
fi
basedir="/root"
shareddir="${basedir}/shared"
workdir="${basedir}/work"
logfile="${shareddir}/out.log"
if ! [ -d "${workdir}" ]; then (mkdir -p "${workdir}"); fi
echo "${basedir}" > "${workdir}/basedir._"
echo "${shareddir}" > "${workdir}/shareddir._"
echo "${logfile}" > "${workdir}/logfile._"
