#!/usr/bin/env python3
"""PvP Server - Tron Light Cycles (TCP, asyncio)"""
import asyncio, json, random, time

PORT = 7777
FPS = 8
W, H = 50, 24
WIN_SCORE = 3
CHARS = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
UP, DOWN, LEFT, RIGHT = 0, 1, 2, 3
DX = [0, 0, -1, 1]
DY = [-1, 1, 0, 0]
OPP_DIR = {0:1, 1:0, 2:3, 3:2}

rooms = {}
online = 0

def gen_code():
    return ''.join(random.choice(CHARS) for _ in range(4))

class Client:
    def __init__(self, reader, writer):
        self.r, self.w = reader, writer
        self.dir_q = []
        self.alive = True
        self.done = asyncio.Event()

    async def send(self, msg):
        if not self.alive: return
        try:
            self.w.write((json.dumps(msg) + '\n').encode())
            await self.w.drain()
        except: self.alive = False

    async def read_loop(self):
        try:
            while self.alive:
                line = await self.r.readline()
                if not line: break
                msg = json.loads(line.decode().strip())
                if msg.get('type') == 'dir':
                    self.dir_q.append(msg['d'])
        except: pass
        self.alive = False

async def run_game(c1, c2, code):
    s1, s2 = 0, 0
    await c1.send({"type":"matched","player":1,"room":code,"online":online})
    await c2.send({"type":"matched","player":2,"room":code,"online":online})
    await asyncio.sleep(0.5)

    while s1 < WIN_SCORE and s2 < WIN_SCORE:
        if not c1.alive or not c2.alive: break

        p1 = {"x":W//4,"y":H//2,"d":RIGHT,"alive":True}
        p2 = {"x":3*W//4,"y":H//2,"d":LEFT,"alive":True}
        grid = [[0]*W for _ in range(H)]
        for x in range(W): grid[0][x]=1; grid[H-1][x]=1
        for y in range(H): grid[y][0]=1; grid[y][W-1]=1
        grid[p1["y"]][p1["x"]] = 2
        grid[p2["y"]][p2["x"]] = 3

        st = {"type":"round_start","p1":p1,"p2":p2,"w":W,"h":H,"s1":s1,"s2":s2}
        await c1.send(st); await c2.send(st)

        for i in range(3, 0, -1):
            cd = {"type":"countdown","n":i}
            await c1.send(cd); await c2.send(cd)
            await asyncio.sleep(0.7)
        await c1.send({"type":"go"}); await c2.send({"type":"go"})
        await asyncio.sleep(0.3)
        c1.dir_q.clear(); c2.dir_q.clear()

        tick, speed = 0, FPS
        while p1["alive"] and p2["alive"]:
            if not c1.alive or not c2.alive: break

            # Process inputs
            if c1.dir_q:
                d = c1.dir_q.pop(0)
                if 0 <= d <= 3 and d != OPP_DIR[p1["d"]]: p1["d"] = d
                c1.dir_q.clear()
            if c2.dir_q:
                d = c2.dir_q.pop(0)
                if 0 <= d <= 3 and d != OPP_DIR[p2["d"]]: p2["d"] = d
                c2.dir_q.clear()

            p1["x"] += DX[p1["d"]]; p1["y"] += DY[p1["d"]]
            p2["x"] += DX[p2["d"]]; p2["y"] += DY[p2["d"]]

            c1c = (p1["x"]<=0 or p1["x"]>=W-1 or p1["y"]<=0 or p1["y"]>=H-1 or grid[p1["y"]][p1["x"]]!=0)
            c2c = (p2["x"]<=0 or p2["x"]>=W-1 or p2["y"]<=0 or p2["y"]>=H-1 or grid[p2["y"]][p2["x"]]!=0)
            if p1["x"]==p2["x"] and p1["y"]==p2["y"]: c1c=c2c=True
            if c1c: p1["alive"]=False
            if c2c: p2["alive"]=False
            if p1["alive"]: grid[p1["y"]][p1["x"]]=2
            if p2["alive"]: grid[p2["y"]][p2["x"]]=3

            t = {"type":"tick","p1x":p1["x"],"p1y":p1["y"],"p1d":p1["d"],"p1a":p1["alive"],
                 "p2x":p2["x"],"p2y":p2["y"],"p2d":p2["d"],"p2a":p2["alive"]}
            await c1.send(t); await c2.send(t)

            tick += 1
            if tick % 60 == 0 and speed < 14: speed += 1
            await asyncio.sleep(1.0 / speed)

        w = 0 if (not p1["alive"] and not p2["alive"]) else (2 if not p1["alive"] else 1)
        if w == 1: s1 += 1
        elif w == 2: s2 += 1
        re = {"type":"round_end","winner":w,"s1":s1,"s2":s2}
        await c1.send(re); await c2.send(re)
        await asyncio.sleep(2.5)

    me = {"type":"match_end","s1":s1,"s2":s2}
    await c1.send(me); await c2.send(me)

match_q = asyncio.Queue()

async def handle_client(reader, writer):
    global online
    online += 1
    c = Client(reader, writer)
    rt = asyncio.create_task(c.read_loop())
    addr = writer.get_extra_info('peername')
    print(f"[+] {addr} connected (online: {online})")

    try:
        line = await asyncio.wait_for(reader.readline(), timeout=15)
        if not line: return
        msg = json.loads(line.decode().strip())

        if msg["type"] == "match":
            await c.send({"type":"waiting","online":online})
            await match_q.put(c)
            await c.done.wait()

        elif msg["type"] == "create":
            code = gen_code()
            while code in rooms: code = gen_code()
            rooms[code] = {"host":c}
            await c.send({"type":"room_created","code":code,"online":online})
            # Wait for guest
            for _ in range(600):  # 60s timeout
                if "guest" in rooms.get(code, {}): break
                if not c.alive: break
                await asyncio.sleep(0.1)
            room = rooms.get(code)
            if room and room.get("guest"):
                await run_game(c, room["guest"], code)
                room["guest"].done.set()
            rooms.pop(code, None)
            c.done.set()

        elif msg["type"] == "join":
            code = msg.get("code","").upper()
            room = rooms.get(code)
            if room and room.get("host") and "guest" not in room:
                room["guest"] = c
                await c.done.wait()
            else:
                await c.send({"type":"error","msg":"Room not found or full"})

    except Exception as e:
        print(f"[!] {addr}: {e}")
    finally:
        online -= 1
        c.alive = False
        rt.cancel()
        try: writer.close()
        except: pass
        print(f"[-] {addr} disconnected (online: {online})")

async def matchmaker():
    while True:
        c1 = await match_q.get()
        if not c1.alive: continue
        c2 = None
        while not c2:
            cand = await match_q.get()
            if cand.alive and c1.alive:
                c2 = cand
            elif not c1.alive:
                if cand.alive: c1 = cand
                else: c1 = await match_q.get()

        code = gen_code()
        async def run(a, b, cd):
            try: await run_game(a, b, cd)
            finally: a.done.set(); b.done.set()
        asyncio.create_task(run(c1, c2, code))

async def main():
    srv = await asyncio.start_server(handle_client, '0.0.0.0', PORT)
    asyncio.create_task(matchmaker())
    print(f"🎮 PvP Server running on port {PORT}")
    async with srv: await srv.serve_forever()

if __name__ == '__main__':
    asyncio.run(main())
