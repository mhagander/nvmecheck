nvme device checker
===================

This is a super trivial check script for NVME devices. It stores a
persistent copy of interesting attributes from the NVME smart-log, and
compares against it. If some values have changed (such as error
counters), an email is sent off with a notification of this.
