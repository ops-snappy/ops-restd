
[Standard REST API] Test Cases
==============================

## Contents

- [REST Full Declarative configuration](#rest-full-declarative-configuration)

## REST Full Declarative configuration
### Objective
The objective of the test case is to verify if the user configuration was set in the OVSDB.

### Requirements
The requirements for this test case are:

- OpenSwitch
- Ubuntu Workstation

### Setup
#### Topology Diagram

```ditaa
    +-------------------+                           +--------------------+
    |                   |                           |       Ubuntu       |
    |    OpenSwitch     |eth0+-----------------+eth1|                    |
    |                   |         link01            |     Workstation    |
    |                   |                           |                    |
    +-------------------+                           +--------------------+
```

### Description
This test case verifies if the configuration was set correctly by comparing user configuration (input) with the output of ovsdb read.

 1. Connect the OpenSwitch to Ubuntu workstation as shown in the topology diagram.
 2. Configure the IPV4 address on the switch management interfaces.
 3. Configure the IPV4 address on the Ubuntu workstation.
 4. This script validates if the input configuration is updated correctly in the OVSDB by comparing output configuration (read from OVSDB after write) with user input configuration.

### Test Result Criteria
#### Test Pass Criteria
The test case is pass if the input configuration matches the output configuration (read from OVSDB after write).

#### Test Fail Criteria
The test case is failing if the input configuration does not match the output configuration (read from OVSDB after write).
