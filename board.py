from machine import UART

NRF_TX  = 32
NRF_RX  = 33

nrf_uart = UART(1, baudrate=1000000, rx=NRF_RX, tx=NRF_TX, rxbuf=8192)#, rts=NRF_RTS, cts=NRF_CTS, flow=UART.RTS | UART.CTS)
