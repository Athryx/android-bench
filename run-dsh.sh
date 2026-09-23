#!/bin/sh

ssh -L 3067:127.0.0.1:3067 claudessh2 'bash -ic "dsh web"'
