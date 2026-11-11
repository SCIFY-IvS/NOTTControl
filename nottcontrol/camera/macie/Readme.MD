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

### Socket receive buffer (required for Init / MSAC)

MSAC and `zmq_server` request a ~**134217 KB** (~128 MiB) socket receive buffer. If `net.core.rmem_max` is the Linux default (~208 KB), Init fails with:

`Unable to set socket receive buffer size at the OS level to 134217 KB`

This is independent of the `/32` address. Raise it **now** (immediate):

```bash
sysctl net.core.rmem_max
sudo sysctl -w net.core.rmem_max=268435456
sudo sysctl -w net.core.rmem_default=134217728
sudo sysctl -w net.core.wmem_max=268435456
```

`rmem_max` is 256 MiB because the kernel doubles `SO_RCVBUF` for bookkeeping. Confirm:

```bash
sysctl net.core.rmem_max net.core.rmem_default
# expect: 268435456 and 134217728  (not 33554432)
```

Then retry Init (close MSAC first if using the GUI).

**Persist:** `/etc/sysctl.conf` is applied last (`99-sysctl.conf`). On nott-server it still has Lucid/Arena `rmem_max=33554432` (32 MiB). Installing as `99-macie-gige.conf` and running `sysctl --system` **reverts** the working values. Install under a name that sorts **after** `99-sysctl.conf`, and apply **only** that file (do not run `sysctl --system`):

```bash
sudo rm -f /etc/sysctl.d/99-macie-gige.conf
sudo install -m 644 99-macie-gige-sysctl.conf /etc/sysctl.d/99-zz-macie-gige.conf
sudo sysctl -p /etc/sysctl.d/99-zz-macie-gige.conf
sysctl net.core.rmem_max
# must be 268435456
```

## MSAC telemetry (calibrated voltages)

Do this **in MSAC**, with `zmq_server` / the H2RG GUI stopped (only one client on the card). IdleMode = Do Nothing (`0x4002` bit3–4 = 0) does **not** clock the telemetry mux (`WAITB`); those readbacks sit at a dummy voltage (often ~−0.014 V). Trust **DAC hex** (`0x6000`…) unless you follow this procedure.

After the measurement, put **Reset per Frame** back (cold science). Reset per Row is only for the mux.

1. **Initialize** the ASIC and confirm it succeeds.
2. **Configuration** tab: change the reset setting from **Reset per Frame** to **Reset per Row**.
3. **Telemetry** tab: choose **Calibrated Voltage** and uncheck **Autoscale**.
4. Click **Calibrate Volts**.
5. **Manual Command** tab: read ASIC address **`h6180`**. The value must be **`2232`**. If not, write `2232` (ASIC destination, then **W**).
6. **Telemetry** tab: uncheck every measurement from **RefSample** downward. Only the **top set of biases** is used.
7. Enable all **Sense_Res_en** checkboxes **except** **Vbiaspower** and **CellDrain**. In **buffered** mode, also disable the sense resistor for **Drain**.
8. Click **Read** on the Telemetry page.

Compare those volts to the programmed DACs (`VReset1` `0x6000`, `DSub1` `0x6002`, `VBiasGate1` `0x6004`, …). If telemetry is still stuck after this, the bias is not making it to the array (or the mux never left idle).
