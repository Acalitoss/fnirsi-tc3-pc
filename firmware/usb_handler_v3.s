// FNIRSI DSO-TC3 V0.3 replacement USB receive handler.
// Protocol 3: remote navigation in modes 1..6; 32 bounded state pages.
// Samples are display displacements, not raw ADC codes.
// 21,00: metadata. Unknown commands and malformed requests are ignored.
push {r4,r5,r6,lr}
cmp r1, #2
blo.w done
mov r4, r0
ldrb r2, [r4]
cmp r2, #0
beq config
cmp r2, #0x20
beq samples
cmp r2, #0x21
beq metadata
cmp r2, #0x22
beq state_page
cmp r2, #0x30
beq remote_key
b done
config:
movs r2, #1
strb r2, [r4]
movs r2, #254
strb r2, [r4, #1]
ldr r5, =0x200006e4
adds r6, r4, #2
movs r3, #4
config_loop:
ldr r2, [r5], #4
lsrs r0, r2, #24
strb r0, [r6], #1
lsrs r0, r2, #16
strb r0, [r6], #1
lsrs r0, r2, #8
strb r0, [r6], #1
strb r2, [r6], #1
subs r3, r3, #1
bne config_loop
movs r1, #18
b transmit
samples:
ldrb r2, [r4, #1]
cmp r2, #20
bhi done
movs r3, #29
cmp r2, #20
bne sample_count
movs r3, #20
sample_count:
movs r5, #0xa5
strb r5, [r4]
movs r5, #0x5a
strb r5, [r4, #1]
strb r2, [r4, #2]
strb r3, [r4, #3]
movs r5, #58
mul r2, r5, r2
ldr r5, =0x20000bfc
add r5, r2
adds r6, r4, #4
lsls r3, r3, #1
adds r1, r3, #4
sample_loop:
ldrb r2, [r5], #1
strb r2, [r6], #1
subs r3, r3, #1
bne sample_loop
b transmit
metadata:
movs r2, #0xa5
strb r2, [r4]
movs r2, #0x5a
strb r2, [r4, #1]
movs r2, #0x21
strb r2, [r4, #2]
movs r2, #3
strb r2, [r4, #3]
ldr r5, =0x20000668
ldr r2, [r5, #0x24]
str r2, [r4, #4]
ldr r2, [r5, #0x28]
str r2, [r4, #8]
ldr r2, [r5, #0x30]
str r2, [r4, #12]
ldr r2, [r5, #0xb0]
str r2, [r4, #16]
ldr r2, =0x20000144
ldr r2, [r2]
str r2, [r4, #20]
movs r1, #24
b transmit
state_page:
ldrb r2, [r4, #1]
cmp r2, #31
bhi done
movs r3, #56
mul r5, r3, r2
ldr r6, =0x20000668
add r5, r6
movs r6, #0xa5
strb r6, [r4]
movs r6, #0x5a
strb r6, [r4, #1]
strb r2, [r4, #2]
strb r3, [r4, #3]
adds r6, r4, #4
movs r1, #60
b sample_loop
remote_key:
ldrb r2, [r4, #1]
cmp r2, #1
beq valid_key
cmp r2, #2
beq valid_key
cmp r2, #4
beq valid_key
cmp r2, #8
beq valid_key
cmp r2, #16
beq valid_key
cmp r2, #32
beq valid_key
cmp r2, #0x84
bne done
valid_key:
ldr r5, =0x20000668
ldr r3, [r5, #0x20]
cmp r3, #1
blo done
cmp r3, #6
bhi done
ldrb r3, [r5, #0x90]
cmp r3, #0
bne key_busy
movs r6, #1
cmp r2, #0x84
bne short_key
movs r2, #4
movs r6, #0xfe
// Clear the DSO's long-key latch, equivalent to releasing the prior key.
ldr r0, =0x20000140
movs r3, #0
strb r3, [r0]
short_key:
strb r2, [r5, #0x91]
movs r2, #1
strb r6, [r5, #0x90]
movs r3, #0
b key_reply
key_busy:
movs r3, #1
key_reply:
movs r2, #0xa5
strb r2, [r4]
movs r2, #0x5a
strb r2, [r4, #1]
movs r2, #0x30
strb r2, [r4, #2]
strb r3, [r4, #3]
movs r1, #4
transmit:
mov r0, r4
pop {r4,r5,r6,lr}
b.w 0x08005158
done:
pop {r4,r5,r6,pc}
