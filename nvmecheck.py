#!/usr/bin/env python3
#
# nvmecheck.py -- super trivial NVME device checker
#
# Run this from cron to get an email when any of the tracked keys in
# the NVME SMART data changes, to catch things like degrading
# hardware.
#

import argparse
import json
import os
import subprocess
import time
import io
import copy
from email.mime.text import MIMEText
import smtplib
import socket


TRACKED_KEYS = ['avail_spare', 'spare_thresh', 'percent_used',
                'unsafe_shutdowns', 'media_errors', 'num_err_log_entries',
                'warning_temp_time', 'critical_comp_time']


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='NVME device checker')
    parser.add_argument(
        '--persist-file',
        type=str,
        default='~/.nvmecheck.json',
        help='File to persist state in',
    )
    parser.add_argument(
        '--minhours',
        type=int,
        default=0,
        help="Only update persistant data if it's older than this many hours",
    )
    parser.add_argument('--fromaddr', type=str, help='From email address')
    parser.add_argument('--toaddr', type=str, help='To email address')

    args = parser.parse_args()

    if os.path.exists(os.path.expanduser(args.persist_file)):
        with open(os.path.expanduser(args.persist_file), 'r') as f:
            persisted = json.load(f)
    else:
        persisted = {
            'when': 0,
            'devices': {},
        }

    updated = copy.deepcopy(persisted)
    out = io.StringIO()
    out.write('NVME data has updated:\n\n')

    j = json.loads(subprocess.run(
        ['nvme', 'list', '-o', 'json'],
        check=True,
        capture_output=True,
    ).stdout)
    for d in j['Devices']:
        p = d['DevicePath']
        jj = json.loads(subprocess.run(
            ['nvme', 'smart-log', p, '-o', 'json'],
            check=True,
            capture_output=True,
        ).stdout)
        kk = {k: jj[k] for k in TRACKED_KEYS}

        if p in updated['devices']:
            # Compare to existing device
            if kk != persisted['devices'][p]:
                # Something changed!
                out.write("For device {}:\n".format(p))
                for k in TRACKED_KEYS:
                    if kk[k] != persisted['devices'][p][k]:
                        out.write("{:20} changed from {} to {}\n".format(
                            k,
                            persisted['devices'][p][k],
                            kk[k],
                        ))
                out.write("\n")

                updated['devices'][p] = kk
        else:
            out.write("Found new device {}\n".format(p))
            updated['devices'][p] = kk

    if persisted != updated:
        # Something changed!
        if args.fromaddr:
            # Send it by email!
            msg = MIMEText(out.getvalue())
            msg['Subject'] = 'NVME report for {} (CONTAINS CHANGES)'.format(
                socket.gethostname())
            msg['From'] = args.fromaddr
            msg['To'] = args.toaddr
            s = smtplib.SMTP('localhost')
            s.send_message(msg)
            s.quit()
        else:
            # If no email is specified, just dump it to stdout
            print(out.getvalue())
    else:
        # Nothing changed, but should we send a status reoprt?
        if args.fromaddr:
            msg = MIMEText('No changes reported to any NVME counters')
            msg['Subject'] = 'NVME report for {}'.format(socket.gethostname())
            msg['From'] = args.fromaddr
            msg['To'] = args.toaddr
            s = smtplib.SMTP('localhost')
            s.send_message(msg)
            s.quit()

    updated['when'] = int(time.time())
    if updated['when'] - persisted['when'] > args.minhours * 3600:
        with open(os.path.expanduser(args.persist_file), 'w') as f:
            json.dump(updated, f)
