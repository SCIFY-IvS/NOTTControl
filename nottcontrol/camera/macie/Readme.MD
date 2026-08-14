This folder contains C++ code that manages the HAWAII science camera, as well as a python interface that communicates to the C++ code using ZMQ.
At the moment, the zmq interface is hardcoded on port 65534 on the same machine (ie. localhost).

In order to compile the C++ code, there are detailed instructions in the MACIE_Installation_notes.txt document. In short:
- Set LD_LIBRARY_PATH:
export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/usr/local/lib/macie_lib
We don't use .bashrc for this as it interferes with other code!
- Compile the C++ code by running the make files under /libmacie and then /macie_exe
- Run the zmq_server executable. As of now, it needs to be run from this folder! So from here execute ./macie_exe/zmq_server

Now you're able to instantiate the macie_interface class and use it to communicate to the camera.

## GigE: MACIE ↔ nott-server (direct link)

Science data must go over a **direct Ethernet cable** from the MACIE GigE port to **nott-server `enp2s0f1`**. Do not put this cable on the lab wall/switch: campus GigE is too slow / lossy for H2RG downloads.

Leave the campus NIC **untouched**. VNC, SSH, and the rest of the instrument LAN stay on `enp2s0f0`.

| Role | Interface | Address |
|------|-----------|---------|
| Campus / VNC / SSH | `enp2s0f0` | `10.33.179.136/24` — **do not change** |
| MACIE GigE (card) | cable → `enp2s0f1` | `10.33.179.135` |
| Direct-link host address (server only) | `enp2s0f1` | `10.33.179.137/32` |

`10.33.179.137` is **not** the card. It is only the server’s address on the camera cable so Linux can ARP. The card stays `10.33.179.135`.

### After reboot (addresses on `enp2s0f1` are not persistent)

```bash
sudo ip addr flush dev enp2s0f1
sudo ip link set enp2s0f1 up
sudo ip addr add 10.33.179.137/32 dev enp2s0f1
sudo ip route replace 10.33.179.135/32 dev enp2s0f1
ping -c 3 10.33.179.135
```

Confirm:

```bash
ip -br link show enp2s0f1
# expect: UP … LOWER_UP

ip route get 10.33.179.135
# expect: … dev enp2s0f1 …

ip route get 10.33.179.1
# expect: … dev enp2s0f0 …   (campus / VNC)
```

Then start `zmq_server` from this folder (`LD_LIBRARY_PATH` as above) and Init from the GUI. Close MSAC first — only one client on the card.

### Do not

- Put a **`10.33.179.0/24`** on `enp2s0f1` (for example `10.33.179.137/24`). That steals the lab subnet from `enp2s0f0` and **drops VNC/SSH**.
- Change or add addresses on **`enp2s0f0` / `10.33.179.136`**.
- Change the MACIE card IP (`10.33.179.135`) for this layout.
- Plug the MACIE Ethernet into the wall when you need science-rate GigE.

### Persist across reboot (nott-server)

Do this **on nott-server**, in a VNC/SSH session that uses `enp2s0f0`. The files live in `network/` next to this readme. They only configure `enp2s0f1`.

```bash
cd /path/to/NOTTControl/nottcontrol/camera/macie/network

sudo install -m 755 macie-gige-up.sh /usr/local/sbin/macie-gige-up.sh
sudo install -m 644 macie-gige.service /etc/systemd/system/macie-gige.service
sudo install -m 644 99-unmanaged-macie.conf /etc/NetworkManager/conf.d/99-unmanaged-macie.conf

# Stop NetworkManager from owning the camera NIC (does not restart NM / VNC)
sudo nmcli device set enp2s0f1 managed no
sudo nmcli general reload

sudo systemctl daemon-reload
sudo systemctl enable --now macie-gige.service
```

Immediately check that campus is still on `enp2s0f0`:

```bash
systemctl status macie-gige.service
ping -c 3 10.33.179.135
ip route get 10.33.179.135
# expect: … dev enp2s0f1 …
ip route get 10.33.179.1
# expect: … dev enp2s0f0 …
```

If VNC drops, on the local console:

```bash
sudo systemctl stop macie-gige.service
sudo ip addr flush dev enp2s0f1
```

Never assign `10.33.179.0/24` to `enp2s0f1` in netplan or NetworkManager.