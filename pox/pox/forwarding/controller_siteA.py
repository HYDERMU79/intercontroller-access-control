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
from pox.lib.packet.arp import arp
from pox.lib.packet.ipv4 import ipv4
import time
import requests
import json
import pox.lib.packet as pkt

log = core.getLogger()

_flood_delay = 0

### CHANGE ### This must be changed before running the program on your own computer ###
# Port and IP of controller at siteB. The port the webserver listens to, and the IP of the machine running the controller.
port_siteB = 8821
ip_siteB = '10.50.10.222'

# The resource at siteA(r1)
r1 = '10.0.0.2'

# The hosts within the network at siteA
file = open('siteAhosts', 'w')
data = ['00:00:00:00:02:00', '00:00:00:00:04:00'] #r1, h1
file.write(str(data))
file.close()

# A list of allowed connections, like the one between the resource at siteA and the user when it is in siteB
file = open('allowedConnections', 'w')
data = [[]]
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

    packet = event.parsed
    
    # Fetching the updated version of the list.
    file = open('siteAhosts', 'r')
    siteAhosts = eval(file.readline())
    file.close()

    # Fetchin the updated version of allowed connections.
    file = open('allowedConnections', 'r')
    allowedConnections = eval(file.readline())
    file.close()

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
      Drops packet.
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

    def isAllowedConnection(source, destination):
      """
      Checks if incoming packets IP source and destination is one of the allowed connections.
      """
      if len(allowedConnections[0]) == 0: #No allowed connections
        return False
      for element in allowedConnections:
        if (element[0] == source and element[1] == destination) or (element[0] == destination and element[1] == source): #Traffic both ways are allowed
          return True
      return False


    if (isinstance(packet.next, ipv4)):#ARP packets are allowed past.
      if(packet.payload.protocol == 1) and (packet.payload.payload.type == 0): 
        #log.debug("ICMP packet ECHO REPLY") 
        pass #ECHO REPLY messages are allowed past.
      else:
        if(str(packet.src) not in siteAhosts): #Packet comes from outside the network.
          #Network openness can be chosen and filtered thereafter here. In this scenario, it is only the resource r1 that has restrictions.
          if((str(packet.next.dstip) == r1) and (isAllowedConnection(str(packet.next.srcip), str(packet.next.dstip)) == False)): #Unless the connection is allowed
            drop()
            return     
        pass
    
    ## Remaining code in this function is unchanged from POX's stock component l2_learning.py
    if not self.transparent:
      if packet.type == packet.LLDP_TYPE or packet.dst.isBridgeFiltered():
        drop()
        return

    if packet.dst.is_multicast:
      flood() 
    else:
      if packet.dst not in self.macToPort: # 4
        flood("Port for %s unknown -- flooding" % (packet.dst,)) # 4a
      else:
        port = self.macToPort[packet.dst]
        if port == event.port: 
          log.warning("Same port for packet from %s -> %s on %s.%s.  Drop."
              % (packet.src, packet.dst, dpid_to_str(event.dpid), port))
          drop(10)
          return

        log.debug("installing flow for %s.%i -> %s.%i" %
                  (packet.src, event.port, packet.dst, port))
        msg = of.ofp_flow_mod()
        msg.match = of.ofp_match.from_packet(packet, event.port)
        msg.idle_timeout = 10
        msg.hard_timeout = 30
        msg.actions.append(of.ofp_action_output(port = port))
        msg.data = event.ofp # 6a
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


def ICAC_communicate_access(json_object):
  """
  Receives msg1, and sends msg2 to controller at siteB.
  """
  file = open('msg2', 'r')
  s = file.read()
  params = {"json_object":s}
  payload = {"method":"send_msg2_to_siteB","id":2, "params":params}
  r = requests.post("http://" + str(ip_siteB) + ":" + str(port_siteB) + "/OF/", data=json.dumps(payload))
  return

def ICAC_configure_access(json_object):
  """
  Receives msg3 from controller at siteB. Extracts information and updates allowedConnection.
  """
  s = json.loads(json_object)
  ip1 = s["message"]["user"]["ipv4-address"]
  ip2 = s["message"]["resources"]["r1"]["ipv4-address"]
  file = open('allowedConnections', 'w')
  data = [[str(ip1), str(ip2)]]
  file.write(str(data))
  file.close() 
  return


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
