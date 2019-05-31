# Copyright 2012 James McCauley
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

"""
A simple JSON-RPC-ish web service for interacting with OpenFlow.

"""

# This file is build upon POXs webservice.py found in github here: 
#
#     https://github.com/noxrepo/pox/blob/eel/pox/openflow/webservice.py



import sys
from pox.lib.util import dpidToStr, strToDPID, fields_of
from pox.core import core
import pox.openflow.libopenflow_01 as of
from pox.openflow.of_json import *
from pox.web.jsonrpc import JSONRPCHandler, make_error
import threading
from datetime import datetime
import requests
import json
from forwarding.controller_siteA import ICAC_configure_access, ICAC_communicate_access
from forwarding.controller_siteB import ICAC_available_resources

log = core.getLogger()


class OFConRequest (object):
  """
  Superclass for requests that send commands to a connection and
  wait for responses.
  """
  def __init__ (self, con, *args, **kw):
    self._response = None
    self._sync = threading.Event()
    self._aborted = False
    self._listeners = None
    self._con = con
    #self._init(*args, **kw)
    core.callLater(self._do_init, args, kw)

  def _do_init (self, args, kw):
    self._listeners = self._con.addListeners(self)
    self._init(*args, **kw)

  def _init (self, *args, **kw):
    #log.warn("UNIMPLEMENTED REQUEST INIT")
    pass

  def get_response (self):
    if not self._sync.wait(5):
      # Whoops; timeout!
      self._aborted = True
      self._finish()
      raise RuntimeError("Operation timed out")
    return self._response

  def _finish (self, value = None):
    if self._response is None:
      self._response = value
    self._sync.set()
    self._con.removeListeners(self._listeners)

  def _result (self, key, value):
    self._finish({'result':{key:value,'dpid':dpidToStr(self._con.dpid)}})


class OFSwitchDescRequest (OFConRequest):
  def _init (self):
    sr = of.ofp_stats_request()
    sr.type = of.OFPST_DESC
    self._con.send(sr)
    self.xid = sr.xid

  def _handle_SwitchDescReceived (self, event):
    if event.ofp.xid != self.xid: return
    r = switch_desc_to_dict(event.stats)
    self._result('switchdesc', r)

  def _handle_ErrorIn (self, event):
    if event.ofp.xid != self.xid: return
    self._finish(make_error("OpenFlow Error", data=event.asString()))


class OFFlowStatsRequest (OFConRequest):
  def _init (self, match=None, table_id=0xff, out_port=of.OFPP_NONE):
    sr = of.ofp_stats_request()
    sr.body = of.ofp_flow_stats_request()
    if match is None:
      match = of.ofp_match()
    else:
      match = dict_to_match(match)
    sr.body.match = match
    sr.body.table_id = table_id
    sr.body.out_port = out_port
    self._con.send(sr)
    self.xid = sr.xid

  def _handle_FlowStatsReceived (self, event):
    if event.ofp[0].xid != self.xid: return
    stats = flow_stats_to_list(event.stats)

    self._result('flowstats', stats)

  def _handle_ErrorIn (self, event):
    if event.ofp.xid != self.xid: return
    self._finish(make_error("OpenFlow Error", data=event.asString()))


class OFSetTableRequest (OFConRequest):

  def clear_table (self, xid = None):
    fm = of.ofp_flow_mod()
    fm.xid = xid
    fm.command = of.OFPFC_DELETE
    self._con.send(fm)
    bar = of.ofp_barrier_request()
    bar.xid = xid
    self._con.send(bar)
    #TODO: Watch for errors on these

  def _init (self, flows = []):
    self.done = False

    xid = of.generate_xid()
    self.xid = xid
    self.clear_table(xid=xid)

    self.count = 1 + len(flows)

    for flow in flows:
      fm = dict_to_flow_mod(flow)
      fm.xid = xid

      self._con.send(fm)
      self._con.send(of.ofp_barrier_request(xid=xid))

  def _handle_BarrierIn (self, event):
    if event.ofp.xid != self.xid: return
    if self.done: return
    self.count -= 1
    if self.count <= 0:
      self._result('flowmod', True)
      self.done = True

  def _handle_ErrorIn (self, event):
    if event.ofp.xid != self.xid: return
    if self.done: return
    self.clear_table()
    self.done = True
    self._finish(make_error("OpenFlow Error", data=event.asString()))


class OFRequestHandler (JSONRPCHandler):

  def _exec_set_table (self, dpid, flows):
    dpid = strToDPID(dpid)
    con = core.openflow.getConnection(dpid)
    if con is None:
      return make_error("No such switch")

    return OFSetTableRequest(con, flows).get_response()

  def _exec_get_switch_desc (self, dpid):
    dpid = strToDPID(dpid)
    con = core.openflow.getConnection(dpid)
    if con is None:
      return make_error("No such switch")

    return OFSwitchDescRequest(con).get_response()

  def _exec_get_flow_stats (self, dpid, *args, **kw):
    dpid = strToDPID(dpid)
    con = core.openflow.getConnection(dpid)
    if con is None:
      return make_error("No such switch")

    return OFFlowStatsRequest(con, *args, **kw).get_response()

  def _exec_get_switches (self):
    return {'result':list_switches()}

  """

  The three functions below are the ones used in this simulation. 
  The messages sent between the controllers(msg1, msg2, msg3) control the access control of the user.

  """


  def _exec_send_msg1_to_siteA (self, json_object):
    #Msg 1 is now sent to controllerA at siteA, which then constructs Msg2
    log.debug("Received msg1 : ")
    log.debug(json_object)
    ICAC_communicate_access(json_object)  
    return {"status":"complete","MSG1 sent to:":"siteA"}
 
  def _exec_send_msg2_to_siteB (self, json_object):
    #Msg 2 is now sent to controllerB at siteB, which then waits for the user to try reaching a resource at siteA
    log.debug("Received msg2 : ")
    log.debug(json_object)
    ICAC_available_resources(json_object)
    return {"status":"complete","MSG2 sent to:":"siteB"}
  
  def _exec_send_msg3_to_siteA (self, json_object):
    #Msg 3 is now sent to controllerA at siteA, which will now make the rules to allow access.
    log.debug("Received msg3 : ")
    log.debug(json_object)
    ICAC_configure_access(json_object)
    return {"status":"complete","MSG3 sent to:":"siteA"}




def launch (username='', password=''):
  def _launch ():
    cfg = {}
    if len(username) and len(password):
      cfg['auth'] = lambda u, p: (u == username) and (p == password)
    core.WebServer.set_handler("/OF/",OFRequestHandler,cfg,True)

  core.call_when_ready(_launch, ["WebServer","openflow"],
                       name = "openflow.webservice")
