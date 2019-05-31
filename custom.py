#!usr/bin/python

from mininet.net import Mininet
from mininet.node import RemoteController
from mininet.cli import CLI
from mininet.log import setLogLevel, info


def MyNetwork():
    net= Mininet(topo=None, build=False)

    ##Add IP address of the machine running the POX controller. Make sure the port numbers are similar to where the controller is running. 
    ##Note that POX's default port is 6633. 
    info("***Adding c1 \n") 
    c1 = net.addController(name='c1',controller=RemoteController,ip='10.50.10.222',port=6633)   
    
    ##Add IP address of the machine running the POX controller. Make sure the port numbers are similar to where the controller is running
    info("***Adding c2 \n") 
    c2 = net.addController(name='c2',controller=RemoteController,ip='10.50.10.222',port=6634)


    info("***Adding switches \n")
    s1=net.addSwitch('s1')
    s2=net.addSwitch('s2')


    info("***Adding user(user in siteB) \n")
    user=net.addHost('user',  mac='00:00:00:00:01:00', ip='10.0.0.1')

    info("***Adding resource r1 and r2 \n")
    r1=net.addHost('r1', mac='00:00:00:00:02:00', ip='10.0.0.2')
    r2=net.addHost('r2', mac='00:00:00:00:03:00', ip='10.0.0.3')

    info("***Adding hosts to act as other users in network \n")
    h1=net.addHost('h1', mac='00:00:00:00:04:00', ip='10.0.0.4')
    h2=net.addHost('h2', mac='00:00:00:00:05:00', ip='10.0.0.5')

    info("***Adding links \n")
    net.addLink(s1,s2)
    net.addLink(r1,s1)
    net.addLink(h1,s1)
    net.addLink(user,s2)
    net.addLink(h2,s2)
    net.addLink(r2,s2)

    net.build()

    info("***Starting switches and controllers \n")
    net.get('s1').start([c1])
    net.get('s2').start([c2])

    c1.start()
    c2.start()

    CLI(net)
    net.stop()

if __name__ == '__main__':
    setLogLevel('info')
    MyNetwork()
