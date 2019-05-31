# intercontroller-access-control

This repository contains all code and files used in my master thesis written during spring 2019.
The purpose behind this code is to validate a data model written in YANG, to ensure that the model can be used to configure access for a user to a resource outside the network it is connected to. The basis of this idea is to use intercontroller communication to improve access control between networks running SDN. The validation was done by running an emulation in Mininet with remote controllers running modified POX controllers. The POX controller can be found at the following link

  https://github.com/noxrepo/pox

***

Before starting, Mininet has to be installed and configured. See link below for step-by-step guide on how to set up Mininet: 

  http://www.brianlinkletter.com/set-up-mininet/

Also, clone or copy the pox part of this repository. Or should you already have the POX repo installed, then add the files mentioned in this repo's POX's readme. Copy them to the same places as in this repo, or do consequent changes to the terminal command, and/or the file-paths in the controller files(seen below).


There are two main files running the logic of the different controllers: 

    controller_siteA
    controller_siteB

In order for the emulation to work, the IP address and port number which the controllers will attempt to communicate with has to be changed within these files. There are appropriate variable names at the top of both files. The IP address is the IP address of the machine running the other controller locally. Say that in controller_siteA, the value of ip_siteB is the IP of the machine running the siteB controller, and vice versa. The port number is the port you tell the webcore component to listen on. Later you will see how to instantiate all components used in this emulation. 

In addition, the custom.py file also has to change the IP addresses in order to reach the remote controllers. These IP addresses are the ones of the machines running the Mininet. While testing for this thesis, both controller ran locally while Mininet ran in a VM in the same machine. The IP is then the IP of this machine, localhost could also work. Remember to set up Mininet properly so that Mininet can reach the local host while running in the VM. 

***

In order to run the simulation: 

1. Start Mininet VM image in whatever VM chosen. 
2. Run both controllers: 
  
    siteA:
      
        pox$ ./pox.py log.level --DEBUG samples.pretty_log web.webcore --port=8820 openflow.webserviceICAC forwarding.controller_siteA 

    siteB:
      
        pox$ ./pox.py log.level --DEBUG samples.pretty_log web.webcore --port=8821 openflow.webserviceICAC forwarding.controller_siteB openflow.of_01 --port=6634

3. Either SSH to the Mininet VM, or do the following commands directly in the Mininet VM:
        
        mininet@mininet.vm:~$ sudo python custom.py

4. In the CLI that pops up after the last command, run pingall to see the current access of all hosts within the network. 
        
        mininet> pingall
        
5. An attempt to contact "the authentication server" will trigger messages to be sent between the controllers. These will be seen in the the terminal of the controllers if they're running with log.level --DEBUG. Here the authentication server 's address is 10.0.0.123.
        
        mininet> user ping -c1 10.0.0.123

6. When the user then pings r1, msg3 will be sent to the controller at siteA which will open access for the user to the resource. 
        
        mininet> user ping -c1 r1

7. The pingall run after this, will show that the user has access. 
        
        mininet> pingall
