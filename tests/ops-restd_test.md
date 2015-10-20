
[Standard REST API] Test Cases
==============================

## Contents

- [REST full declarative configuration](#rest-full-declarative-configuration)

## REST full declarative configuration
### Objective
The objective of the test case is to verify if the user configuration is set in the OVSDB.

### Requirements
The requirements for this test case are:

- OpenSwitch
- Ubuntu Workstation

### Setup
#### Topology diagram

```ditaa
    +-------------------+                           +--------------------+
    |                   |                           |       Ubuntu       |
    |    OpenSwitch     |eth0+-----------------+eth1|                    |
    |                   |         link01            |     Workstation    |
    |                   |                           |                    |
    +-------------------+                           +--------------------+
```

### Description
This test case verifies if the configuration was set correctly by comparing user configuration (input) with the output of OVSDB read.

 1. Connect OpenSwitch to the Ubuntu workstation as shown in the topology diagram.
 2. Configure the IPV4 address on the switch management interfaces.
 3. Configure the IPV4 address on the Ubuntu workstation.
 4. This script validates if the input configuration is updated correctly in the OVSDB by comparing output configuration (read from OVSDB after write) with user input configuration.

### Test result criteria
#### Test pass criteria
The test case passes if the input configuration matches the output configuration (read from OVSDB after write).

#### Test fail criteria
The test case is failing if the input configuration does not match the output configuration (read from OVSDB after write).
