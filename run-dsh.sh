#!/bin/sh

ssh -L 3080:127.0.0.1:3080 claudessh2 'bash -ic "dsh web"'
