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

def configure_server_port():
    # Configure 1 server IP interface and no default gateway on port 1.
    # First the default gw
    pcfg = b2b_port_add(eth_port=0, def_gw=Ip(ip_version=IPV4, ip_v4=0))

    intf1 = (Ip(ip_version=IPV4, ip_v4=b2b_mask(eth_port=0, intf_idx=0)),
             Ip(ip_version=IPV4, ip_v4=b2b_mask(eth_port=1, intf_idx=0)),
             b2b_count(eth_port=0, intf_idx=0))
    b2b_port_add_intfs(pcfg, [intf1])

    # Ask WARP17 to add them to the config.
    err = warp17_method_call(warp17_host, warp17_port, Warp17_Stub, 'ConfigurePort', pcfg)
    if err.e_code != 0:
        die('Error configuring port 1.')

    # Prepare the L4 Server config (eth_port 1)
    # ports in the range: [101, 200]
    port_range=L4PortRange(l4pr_start=101, l4pr_end=200)
    l4_scfg = L4Server(l4s_proto=TCP,
                       l4s_tcp_udp=TcpUdpServer(tus_ports=port_range))

    # Prepare the HTTP Server config
    http_scfg = AppServer(as_app_proto=HTTP,
                          as_http=HttpServer(hs_resp_code=OK_200,
                                             hs_resp_size=2048))

    # The server test case criteria is to have all servers in listen state.
    # However, server test cases are special and keep running even after the
    # PASS criteria is met
    scrit = TestCriteria(tc_crit_type=SRV_UP, tc_srv_up=100)

    # Put the whole test case config together
    scfg = TestCase(tc_type=SERVER, tc_eth_port=1, tc_id=0,
                    tc_server=Server(srv_ips=b2b_sips(eth_port=1, ip_count=1),
                                     srv_l4=l4_scfg,
                                     srv_app=http_scfg),
                    tc_criteria=scrit,
                    tc_async=False)

    # Ask WARP17 to add the test case config
    err = warp17_method_call(warp17_host, warp17_port, Warp17_Stub, 'ConfigureTestCase', scfg)
    if err.e_code != 0:
        die('Error configuring server test case.')

    print 'Servers configured successfully!\n'

def start_server_port():
    err = warp17_method_call(warp17_host, warp17_port, Warp17_Stub, 'PortStart',
                             PortArg(pa_eth_port=1))
    if err.e_code != 0:
        die('Error starting server test cases.')

    print 'Servers started successfully!\n'


def stop_server_port():
    err = warp17_method_call(warp17_host, warp17_port, Warp17_Stub, 'PortStop',
                             PortArg(pa_eth_port=1))
    if err.e_code != 0:
        die('Error stopping server test cases.')

    print 'Servers stopped successfully!\n'

def run_test():
    ''' Assumes client and server seperated '''

    warp17_pid = init_test()
    configure_server_port()

    start_server_port()

    time.sleep(400)

    stop_server_port()

    # Cleanup: Ask WARP17 to stop
    warp17_stop(env, warp17_pid)

if __name__ == '__main__':
    run_test()

