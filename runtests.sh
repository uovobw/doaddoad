#!/bin/sh

if [ ! -x "/usr/bin/nosetests" ]; then
	echo "You need to install python-nose";
	exit 1;
else
	/usr/bin/nosetests test;
fi
