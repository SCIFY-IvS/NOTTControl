from netmiko import ConnectHandler

class NetGearInterface():
    def __init__(self):
            netgear_switch = {
                'device_type': 'netgear_prosafe',
                'host':   '10.33.179.171',
                'username': 'admin',
                'password': 'L@boAcc3ss!'
            }

            self._net_connect = ConnectHandler(**netgear_switch)
            self._net_connect.keepalive = 30

    
    def is_power_enabled(self, port: int) -> bool:
          if not 1 <= port <= 8:
                raise Exception("Invalid port number")
          
          command = f"show power inline interface g{port}"
          answer = self._net_connect.send_command(command)
          print(answer)

          lines = answer.splitlines()
          line = lines[3]
          tokens = line.split()
          state = tokens[1]

          result = True if state == "Auto" else False
          return result
    
    def toggle_power(self, port:int, power:bool):
          if not 1 <= port <= 8:
                raise Exception("Invalid port number")
          #self._net_connect.config_mode() is the normal netmiko way to do this
          #It doesn't work because the check_string should be "(config)#" not "(Config)#"
          self._net_connect.send_command("config", expect_string= "")
          if not self._is_in_config_mode():
                raise Exception("Could not go to config mode")
          
          self._net_connect.send_command(f"interface g{port}", expect_string= "")
          if not self._is_in_config_interface_mode():
                raise Exception("Could not go to config interface mode")
          
          value = "auto" if power else "never"
          self._net_connect.send_command(f"power inline {value}")
          self._net_connect.send_command("exit", expect_string = "")
          self._net_connect.send_command("exit", expect_string = "")

          if self._is_in_config_mode():
                raise Exception("Could not leave config mode")
    
    def _is_in_config_mode(self):
          return self._net_connect.check_config_mode("(config)#")
    
    def _is_in_config_interface_mode(self):
          return self._net_connect.check_config_mode("(config-if)#")
          