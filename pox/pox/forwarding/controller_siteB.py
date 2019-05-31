# Copyright 2011-2012 James McCauley
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at:
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


# This file is build upon POXs l2_learning.py found in github here: 
#
#     https://github.com/noxrepo/pox/blob/eel/pox/forwarding/l2_learning.py
#
# Please use this link to find documentation on the part of the code 
# relevant to the layer 2 learning switch.

from pox.core import core
import pox.openflow.libopenflow_01 as of
from pox.lib.util import dpid_to_str, str_to_dpid
from pox.lib.util import str_to_bool
import time
import requests
import json
from pox.lib.addresses import *
from pox.lib.packet.arp import arp
from pox.lib.packet.ipv4 import ipv4

log = core.getLogger()

_flood_delay = 0

### CHANGE ### This must be changed before running the program on your own computer ###
# Port and IP of controller at siteA. The port the webserver listens to, and the IP of the machine running the controller.
port_siteA = 8820
ip_siteA = '10.50.10.222'

# The user at stage 2.
user = EthAddr('00:00:00:00:01:00')

# The address representing the Authentication Server
authentication_server = '10.0.0.123'

# The resource at siteB(r2)
r2 = '10.0.0.3'

start_time_msg1 = 0
start_time_msg3 = 0


# The list of resources, known to siteB, that user has access to in siteA.
file = open('resources', 'w')
data  = []
file.write(str(data)) 
file.close()

# The hosts within the network at siteB
file = open('siteBhosts', 'w')
data = ['00:00:00:00:01:00', '00:00:00:00:03:00', '00:00:00:00:05:00'] #user, r2, h2
file.write(str(data))
file.close()

class LearningSwitch (object):
 
  def __init__ (self, connection, transparent):
    self.connection = connection
    self.transparent = transparent

    self.macToPort = {}

    connection.addListeners(self)

    self.hold_down_expired = _flood_delay == 0

    log.debug("Initializing LearningSwitch, transparent=%s",
              str(self.transparent))

  def _handle_PacketIn (self, event):
    """
    Handle packet in messages from the switch.
    """

    # Fetchin the updated version of the list of the users resources at siteA
    file = open('resources', 'r')
    resources = eval(file.readline())
    file.close()

    # Fetchin the updated version of the list of hosts at siteB
    file = open('siteBhosts', 'r')
    siteBhosts = eval(file.readline())
    file.close()

    packet = event.parsed

    global start_time_msg1, start_time_msg3

    def flood (message = None):
      """ 
      Floods packet. 
      """

      msg = of.ofp_packet_out()
      if time.time() - self.connection.connect_time >= _flood_delay:

        if self.hold_down_expired is False:
          self.hold_down_expired = True
          log.info("%s: Flood hold-down expired -- flooding",
              dpid_to_str(event.dpid))
        if message is not None: log.debug(message)
        msg.actions.append(of.ofp_action_output(port = of.OFPP_FLOOD))
      else:
        pass
      msg.data = event.ofp
      msg.in_port = event.port
      self.connection.send(msg)


    def drop (duration = None):
      """
      Drops this packet and optionally installs a flow to continue
      dropping similar ones for a while
      """

      if duration is not None:
        if not isinstance(duration, tuple):
          duration = (duration,duration)
        msg = of.ofp_flow_mod()
        msg.match = of.ofp_match.from_packet(packet)
        msg.idle_timeout = duration[0]
        msg.hard_timeout = duration[1]
        msg.buffer_id = event.ofp.buffer_id
        self.connection.send(msg)
      elif event.ofp.buffer_id is not None:
        msg = of.ofp_packet_out()
        msg.buffer_id = event.ofp.buffer_id
        msg.in_port = event.port
        self.connection.send(msg)


    self.macToPort[packet.src] = event.port


    if (isinstance(packet.next, ipv4)): #ARP packets are allowed past.
      if(packet.payload.protocol == 1) and (packet.payload.payload.type == 0):
        #log.debug("ICMP packet ECHO REPLY") 
        pass #ECHO REPLY messages are allowed past.
      else:
        if(str(packet.src) not in siteBhosts): #Packet comes from outside the network.
          #Network openness can be chosen and filtered thereafter here. In this scenario, it is only the resource r2 that has restrictions.
          if(str(packet.next.dstip) == r2):
            drop()
            return
        pass

    if (packet.src == user) and (isinstance(packet.next, arp)) and (packet.next.protodst == authentication_server):
      #User at siteB attempts to contact address reserved for Authentication Server.
      if (time.time() - start_time_msg1) > 8:
        log.info("User accesses network, contacting authentication server")
        log.info("Sending msg1 to controller_siteA")
        file = open('msg1', 'r')
        s = file.read()
        params = {"json_object":s}
        payload = {"method":"send_msg1_to_siteA","id":1, "params":params}
        r = requests.post("http://" + str(ip_siteA) + ":" + str(port_siteA) + "/OF/", data=json.dumps(payload))
      start_time_msg1 = time.time()

    if (packet.src == user) and ( ((isinstance(packet.next, arp)) and (str(packet.next.protodst) in resources) ) or ( (isinstance(packet.next, ipv4)) and (str(packet.next.dstip) in resources)) ):
      #User at siteB attempts to contact a known resource at siteA.
      if (time.time() - start_time_msg3) > 8:
        log.info("User accesses known resource at siteA")
        log.info("Sending msg3 to controller_siteA")
        file = open('msg3', 'r')
        s = file.read()
        params = {"json_object":s}
        payload = {"method":"send_msg3_to_siteA","id":3, "params":params}
        r = requests.post("http://" + str(ip_siteA) + ":" + str(port_siteA) + "/OF/", data=json.dumps(payload))
      start_time_msg3 = time.time()

    ## Remaining code in this function is unchanged from POX's stock component l2_learning.py
    if not self.transparent:
      if packet.type == packet.LLDP_TYPE or packet.dst.isBridgeFiltered():
        log.info(packet.payload)
        drop() 
        return

    if packet.dst.is_multicast:
      flood() 
    else:
      if packet.dst not in self.macToPort:
        flood("Port for %s unknown -- flooding" % (packet.dst,)) 
      else:
        port = self.macToPort[packet.dst]
        if port == event.port:
          return
    
        #log.debug("installing flow for %s.%i -> %s.%i" %
        #          (packet.src, event.port, packet.dst, port))
        msg = of.ofp_flow_mod()
        msg.match = of.ofp_match.from_packet(packet, event.port)
        msg.idle_timeout = 10
        msg.hard_timeout = 30
        msg.actions.append(of.ofp_action_output(port = port))
        msg.data = event.ofp 
        self.connection.send(msg)



class l2_learning (object):
  """
  Waits for OpenFlow switches to connect and makes them learning switches.
  """

  def __init__ (self, transparent, ignore = None):
    """
    Initialize

    See LearningSwitch for meaning of 'transparent'
    'ignore' is an optional list/set of DPIDs to ignore
    """

    core.openflow.addListeners(self)
    self.transparent = transparent
    self.ignore = set(ignore) if ignore else ()


  def _handle_ConnectionUp (self, event):
    if event.dpid in self.ignore:
      log.debug("Ignoring connection %s" % (event.connection,))
      return
    log.debug("Connection %s" % (event.connection,))

    LearningSwitch(event.connection, self.transparent)


def ICAC_available_resources(json_object):  
  """
  Receives msg2 and updates list of known resources user has access to.
  """
  log.info("Updates list of known resources")
  file = open('resources', 'r')
  resources = eval(file.readline())
  s=json.loads(json_object)
  for element in s["message"]["resources"]:
    ip =s["message"]["resources"][element]["ipv4-address"]
    if str(ip) not in resources:
      file.close()
      log.info("Adds resource to list, IP = " + str(ip))
      resources.append(str(ip))
      file = open('resources', 'w')
      file.write(str(resources))
  file.close()


def launch (transparent=False, hold_down=_flood_delay, ignore = None):
  """
  Starts an L2 learning switch.
  """
  try:
    global _flood_delay
    _flood_delay = int(str(hold_down), 10)
    assert _flood_delay >= 0
  except:
    raise RuntimeError("Expected hold-down to be a number")

  if ignore:
    ignore = ignore.replace(',', ' ').split()
    ignore = set(str_to_dpid(dpid) for dpid in ignore)

  core.registerNew(l2_learning, str_to_bool(transparent), ignore)
