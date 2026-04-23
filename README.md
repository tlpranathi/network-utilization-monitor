# SDN Network Monitoring and Traffic Control using Ryu

## Overview

This project demonstrates a Software Defined Networking (SDN) system using the Ryu controller and Mininet. The controller centrally manages the network by installing flow rules, monitoring traffic, and enforcing policies such as host blocking.

## Features

- Centralized control using Ryu SDN controller
- Virtual network topology using Mininet
- Layer 2 switching with MAC learning
- Traffic monitoring using flow statistics
- Bandwidth calculation (Mbps)
- Host-based traffic blocking using MAC address
- CSV logging of network statistics

## Technologies Used

- Python
- Ryu Controller
- Mininet
- OpenFlow Protocol

## Project Structure

- controller.py - Ryu controller implementation
- topology.py - Mininet topology definition
- traffic_log.csv - Generated traffic statistics log

## How It Works

1. Mininet creates a virtual network with hosts and a switch.
2. The Ryu controller connects to the switch using OpenFlow.
3. The controller installs flow rules dynamically based on traffic.
4. MAC learning is used to perform switching.
5. Flow statistics are collected to monitor traffic.
6. A high-priority drop rule blocks traffic from a specific host.

## Blocking Mechanism

- Traffic from a specific MAC address is blocked.
- A high-priority flow rule with no actions is installed.
- This ensures packets are dropped directly at the switch.

Example:

priority=100, eth_src=00:00:00:00:00:03, actions=drop

## Running the Project

### Step 1: Clean Mininet

sudo mn -c

### Step 2: Start Controller

python -m ryu.cmd.manager controller.py

### Step 3: Start Mininet

sudo mn --custom topology.py --topo mytopo --controller=remote --switch=ovsk,protocols=OpenFlow13

## Testing

### Ping Test

mininet> pingall

Expected:
- Communication between allowed hosts works
- Blocked host cannot communicate

### Flow Table

mininet> sh ovs-ofctl -O OpenFlow13 dump-flows s1

## Output

- Flow statistics printed in terminal
- Traffic data saved in traffic_log.csv

## Conclusion

This project demonstrates how SDN enables flexible and centralized network management. It shows how traffic can be monitored and controlled dynamically using programmable controllers.
