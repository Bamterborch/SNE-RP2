import sys
import time

sys.path.append('../../python')
sys.path.append('../../api/generated/py')
sys.path.append('../../ut/lib')

from warp17_api import *

# We hijack a bit the back2back definitions that we use for testing.
# Ideally the user should have his own ways scripting the configured values.
from b2b_setup import *

from warp17_common_pb2    import *
from warp17_l3_pb2        import *
from warp17_server_pb2    import *
from warp17_client_pb2    import *
from warp17_app_http_pb2  import *
from warp17_test_case_pb2 import *
from warp17_service_pb2   import *

def die(msg):
    sys.stderr.write(msg + ' Should cleanup but we just exit..\n')
    sys.exit(1)

def init_test():
    # Configure the WARP17 mandatory environment variables. These could also be
    # set outside the script (through normal env variables) but for this example
    # we do it here..

    # Save the hostname and tcp port WARP17 listens on. Also the env.
    global warp17_host
    global warp17_port
    global env

    env = Warp17Env(path='./nikhef.ini')

    # First start WARP17 on the local machine, default IP and port.
    exec_bin = '../../build/warp17'
    warp17_host = env.get_host_name()
    warp17_port = env.get_rpc_port()

    # Ask for the output log to go to /tmp/nikhef.out
    # Returns the process id of WARP17.
    # This will throw an exception if the output file can't be created or if
    # WARP17 can't be started.
    warp17_pid = warp17_start(env=env, exec_file=exec_bin,
                              output_args=Warp17OutputArgs(out_file='/tmp/nikhef.out'))

    # Now wait for WARP17 to finish initializing
    # This will exit if WARP17 fails to initialize
    warp17_wait(env)
    return warp17_pid

def configure_client_port():
    # Configure 1 client IP interface and no default gateway on port 0.
    # First the default gw
    pcfg = b2b_port_add(eth_port=0, def_gw =Ip(ip_version=IPV4, ip_v4=0))

    intf1 = (Ip(ip_version=IPV4, ip_v4=10.10.10.20),
             Ip(ip_version=IPV4, ip_v4=b2b_mask(eth_port=0, intf_idx=0)),
             b2b_count(eth_port=0, intf_idx=0))
    b2b_port_add_intfs(pcfg, [intf1])

    # Ask WARP17 to add them to the config.
    err = warp17_method_call(warp17_host, warp17_port, Warp17_Stub, 'ConfigurePort', pcfg)
    if err.e_code != 0:
        die('Error configuring port 0.')

    # Prepare the L4 Client config (eth_port 0)
    # source ports in the range: [10001, 30000]
    # destination ports in the range: [101, 200]
    # In total (per client IP): 2M sessions.
    # In total: 4M sessions
    sport_range=L4PortRange(l4pr_start=10001, l4pr_end=30000)
    dport_range=L4PortRange(l4pr_start=101, l4pr_end=200)
    l4_ccfg = L4Client(l4c_proto=TCP,
                       l4c_tcp_udp=TcpUdpClient(tuc_sports=sport_range,
                                                tuc_dports=dport_range))

    rate_ccfg = RateClient(rc_open_rate=Rate(),  # no rate limiting
                           rc_close_rate=Rate(), # no rate limiting
                           rc_send_rate=Rate())  # no rate limiting

    delay_ccfg = DelayClient(dc_init_delay=Delay(d_value=5),
                             dc_uptime=Delay(d_value=10),   # clients stay up for 40s
                             dc_downtime=Delay(d_value=1)) # clients reconnect after 10s

    # Prepare the HTTP Client config
    http_ccfg = AppClient(ac_app_proto=HTTP,
                          ac_http=HttpClient(hc_req_method=GET,
                                             hc_req_object_name='/index.html',
                                             hc_req_host_name='10.10.10.10',
                                             hc_req_size=2048)) # configure HTTP requests of size 2K

    # Prepare the Client test case criteria.
    # Let the test case run for 5 minutes.
    ccrit = TestCriteria(tc_crit_type=RUN_TIME, tc_run_time_s=300)

    # Put the whole test case config together.
    ccfg = TestCase(tc_type=CLIENT, tc_eth_port=0,
                    tc_id=0,
                    tc_client=Client(cl_src_ips=10.10.10.20,
                                     cl_dst_ips=10.10.10.10,
                                     cl_l4=l4_ccfg,
                                     cl_rates=rate_ccfg,
                                     cl_delays=delay_ccfg,
                                     cl_app=http_ccfg),
                    tc_criteria=ccrit,
                    tc_async=True)

    # Ask WARP17 to add the test case config
    err = warp17_method_call(warp17_host, warp17_port, Warp17_Stub, 'ConfigureTestCase', ccfg)
    if err.e_code != 0:
        die('Error configuring client test case.')

    print 'Clients configured successfully!\n'

def start_client_port():
    err = warp17_method_call(warp17_host, warp17_port, Warp17_Stub, 'PortStart',
                             PortArg(pa_eth_port=0))
    if err.e_code != 0:
        die('Error starting client test cases.')

    print 'Clients started successfully!\n'

def check_stats():
    # Just check client stats a couple of times (once a second and stop
    # afterwards)..
    for i in range(0, 10):
        client_result = warp17_method_call(warp17_host, warp17_port, Warp17_Stub,
                                           'GetTestStatus',
                                           TestCaseArg(tca_eth_port=0,
                                                       tca_test_case_id=0))
        if client_result.tsr_error.e_code != 0:
            die('Error fetching client test case stats.')

        print 'Client test case state: ' + str(client_result.tsr_state) + '\n'
        print 'Global stats:'
        print client_result.tsr_stats.tcs_client
        print 'Rate stats:'
        print client_result.tsr_rate_stats
        print 'HTTP Client stats:'
        print client_result.tsr_app_stats.tcas_http

        time.sleep(1)

def stop_client_port():
    err = warp17_method_call(warp17_host, warp17_port, Warp17_Stub, 'PortStop',
                             PortArg(pa_eth_port=0))
    if err.e_code != 0:
        die('Error stopping client test cases.')

    print 'Clients stopped successfully!\n'

 def run_test():
    ''' assumes client to server connection over 40Gb interfaces '''
    ''' This is the client config '''
    
    warp17_pid = init_test()
    configure_client_port()

    start_client_port()

    check_stats()

    stop_client_port()

    # Cleanup: Ask WARP17 to stop
    warp17_stop(env, warp17_pid)

if __name__ == '__main__':
    run_test()

