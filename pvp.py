#!/usr/bin/env python3
"""
/pvp - Claude Code Battle Arena (Online Client)
Tron Light Cycles - ネット対戦
"""
import curses, socket, json, threading, queue, time, sys, argparse

SERVER = "5.78.72.154"
PORT = 7777
UP, DOWN, LEFT, RIGHT = 0, 1, 2, 3

C_BG, C_P1, C_P2, C_WALL, C_TEXT, C_WIN, C_TITLE, C_DIM = 1,2,3,4,5,6,7,8

def init_colors():
    curses.start_color(); curses.use_default_colors()
    curses.init_pair(C_P1, curses.COLOR_CYAN, curses.COLOR_CYAN)
    curses.init_pair(C_P2, curses.COLOR_YELLOW, curses.COLOR_YELLOW)
    curses.init_pair(C_WALL, curses.COLOR_WHITE, curses.COLOR_WHITE)
    curses.init_pair(C_TEXT, curses.COLOR_WHITE, -1)
    curses.init_pair(C_WIN, curses.COLOR_YELLOW, -1)
    curses.init_pair(C_TITLE, curses.COLOR_CYAN, -1)
    curses.init_pair(C_DIM, curses.COLOR_WHITE, -1)

class NetClient:
    def __init__(self, server, port):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(10)
        self.sock.connect((server, port))
        self.sock.settimeout(None)
        self.inbox = queue.Queue()
        self.alive = True
        self.buf = b""
        t = threading.Thread(target=self._recv_loop, daemon=True)
        t.start()

    def _recv_loop(self):
        try:
            while self.alive:
                data = self.sock.recv(4096)
                if not data:
                    self.alive = False; break
                self.buf += data
                while b'\n' in self.buf:
                    line, self.buf = self.buf.split(b'\n', 1)
                    msg = json.loads(line.decode())
                    self.inbox.put(msg)
        except:
            self.alive = False

    def send(self, msg):
        try: self.sock.sendall((json.dumps(msg)+'\n').encode())
        except: self.alive = False

    def poll(self):
        msgs = []
        while not self.inbox.empty():
            msgs.append(self.inbox.get_nowait())
        return msgs

    def close(self):
        self.alive = False
        try: self.sock.close()
        except: pass

# ===== DRAWING =====
def draw_box(scr, y, x, h, w):
    for i in range(w):
        scr.addch(y, x+i, '▓', curses.color_pair(C_WALL)|curses.A_DIM)
        scr.addch(y+h-1, x+i, '▓', curses.color_pair(C_WALL)|curses.A_DIM)
    for i in range(h):
        scr.addch(y+i, x, '▓', curses.color_pair(C_WALL)|curses.A_DIM)
        scr.addch(y+i, x+w-1, '▓', curses.color_pair(C_WALL)|curses.A_DIM)

def draw_scores(scr, s1, s2, me, row, cols):
    lbl1 = "⬤ YOU" if me == 1 else "  P1"
    lbl2 = "⬤ YOU" if me == 2 else "  P2"
    x = max(0, (cols - 40) // 2)
    scr.addstr(row, x, f" P1 ", curses.color_pair(C_P1)|curses.A_BOLD)
    for i in range(3):
        scr.addstr('● ' if i < s1 else '○ ', curses.color_pair(C_P1))
    scr.addstr("  vs  ")
    scr.addstr(f"P2 ", curses.color_pair(C_P2)|curses.A_BOLD)
    for i in range(3):
        scr.addstr('● ' if i < s2 else '○ ', curses.color_pair(C_P2))
    if me:
        tag = "  (あなた: P" + str(me) + ")"
        scr.addstr(tag, curses.color_pair(C_DIM)|curses.A_DIM)

def center(scr, row, text, attr=0):
    _, cols = scr.getmaxyx()
    x = max(0, (cols - len(text)) // 2)
    try: scr.addstr(row, x, text, attr)
    except curses.error: pass

# ===== SCREENS =====
def show_title(scr):
    scr.clear()
    rows, cols = scr.getmaxyx()
    art = [
        "╔═══════════════════════════════════════╗",
        "║                                       ║",
        "║          ⚡  / p v p  ⚡              ║",
        "║     CLAUDE CODE BATTLE ARENA           ║",
        "║                                       ║",
        "║        ━━ TRON LIGHT CYCLES ━━         ║",
        "║          ⚡ ONLINE BATTLE ⚡            ║",
        "║                                       ║",
        "║     1. ⚡ すぐ対戦 (ランダムマッチ)    ║",
        "║     2. 🔑 部屋を作る                   ║",
        "║     3. 🚪 部屋に入る                   ║",
        "║     Q. 終了                            ║",
        "║                                       ║",
        "╚═══════════════════════════════════════╝",
    ]
    sy = max(0, (rows - len(art)) // 2)
    for i, line in enumerate(art):
        x = max(0, (cols - 41) // 2)
        if '⚡' in line and 'pvp' in line:
            attr = curses.color_pair(C_WIN)|curses.A_BOLD
        elif 'ARENA' in line or 'TRON' in line:
            attr = curses.color_pair(C_TITLE)|curses.A_BOLD
        elif 'ONLINE' in line:
            attr = curses.color_pair(C_WIN)
        else:
            attr = curses.color_pair(C_TEXT)
        try: scr.addstr(sy+i, x, line, attr)
        except curses.error: pass
    scr.refresh()

    while True:
        k = scr.getch()
        if k == ord('1'): return 'match'
        if k == ord('2'): return 'create'
        if k == ord('3'): return 'join'
        if k in (ord('q'), ord('Q'), 27): return 'quit'

def get_room_code(scr):
    rows, cols = scr.getmaxyx()
    scr.clear()
    center(scr, rows//2 - 2, "ルームコードを入力 (4文字):", curses.color_pair(C_TEXT))
    center(scr, rows//2, "____", curses.color_pair(C_TITLE)|curses.A_BOLD)
    center(scr, rows//2 + 3, "ESC: 戻る", curses.color_pair(C_DIM))
    scr.refresh()

    code = ""
    cx = (cols - 4) // 2
    curses.echo()
    curses.curs_set(1)
    while len(code) < 4:
        k = scr.getch()
        if k == 27:
            curses.noecho(); curses.curs_set(0)
            return None
        if k in (curses.KEY_BACKSPACE, 127, 8) and code:
            code = code[:-1]
        elif 32 < k < 127 and len(code) < 4:
            code += chr(k).upper()
        scr.addstr(rows//2, cx, code.ljust(4, '_'), curses.color_pair(C_TITLE)|curses.A_BOLD)
        scr.refresh()
    curses.noecho(); curses.curs_set(0)
    return code

def show_status(scr, text, sub=""):
    rows, cols = scr.getmaxyx()
    scr.clear()
    center(scr, rows//2 - 1, text, curses.color_pair(C_TEXT))
    if sub:
        center(scr, rows//2 + 1, sub, curses.color_pair(C_DIM)|curses.A_DIM)
    center(scr, rows//2 + 3, "Q: キャンセル", curses.color_pair(C_DIM))
    scr.refresh()

# ===== GAME RENDERING =====
def game_loop(scr, net, me):
    """Main game rendering loop. me = 1 or 2."""
    curses.curs_set(0)
    scr.nodelay(True)
    scr.timeout(50)

    gw, gh = 50, 24
    grid = None
    p1, p2 = None, None
    s1, s2 = 0, 0
    phase = "waiting"  # waiting, countdown, playing, round_end, match_end

    # Key mappings (always WASD for YOUR controls)
    my_keys = {
        ord('w'): UP, ord('a'): LEFT, ord('s'): DOWN, ord('d'): RIGHT,
        curses.KEY_UP: UP, curses.KEY_LEFT: LEFT, curses.KEY_DOWN: DOWN, curses.KEY_RIGHT: RIGHT,
        ord('i'): UP, ord('j'): LEFT, ord('k'): DOWN, ord('l'): RIGHT,
    }

    while net.alive:
        rows, cols = scr.getmaxyx()
        ox = max(0, (cols - gw) // 2)
        oy = 2

        # Keyboard
        while True:
            k = scr.getch()
            if k == -1: break
            if k in (ord('q'), ord('Q'), 27):
                return
            if k in my_keys and phase == "playing":
                net.send({"type":"dir","d":my_keys[k]})

        # Network messages
        for msg in net.poll():
            t = msg["type"]

            if t == "round_start":
                gw, gh = msg["w"], msg["h"]
                p1 = msg["p1"]; p2 = msg["p2"]
                s1 = msg["s1"]; s2 = msg["s2"]
                grid = [[0]*gw for _ in range(gh)]
                for x in range(gw): grid[0][x]=1; grid[gh-1][x]=1
                for y in range(gh): grid[y][0]=1; grid[y][gw-1]=1
                grid[p1["y"]][p1["x"]] = 2
                grid[p2["y"]][p2["x"]] = 3
                phase = "countdown"
                ox = max(0, (cols - gw) // 2)

            elif t == "countdown":
                scr.clear()
                draw_scores(scr, s1, s2, me, 0, cols)
                if grid:
                    draw_box(scr, oy, ox, gh, gw)
                center(scr, rows//2, str(msg["n"]), curses.color_pair(C_WIN)|curses.A_BOLD)
                scr.refresh()

            elif t == "go":
                phase = "playing"
                scr.clear()
                draw_scores(scr, s1, s2, me, 0, cols)
                if grid: draw_box(scr, oy, ox, gh, gw)
                center(scr, rows//2, "GO!", curses.color_pair(C_WIN)|curses.A_BOLD)
                center(scr, rows-1, "WASD / Arrow / IJKL: 移動   Q: 終了", curses.color_pair(C_DIM)|curses.A_DIM)
                scr.refresh()

            elif t == "tick" and grid:
                px1, py1 = msg["p1x"], msg["p1y"]
                px2, py2 = msg["p2x"], msg["p2y"]
                a1, a2 = msg["p1a"], msg["p2a"]
                d1, d2 = msg["p1d"], msg["p2d"]

                if a1 and 0 < py1 < gh-1 and 0 < px1 < gw-1:
                    grid[py1][px1] = 2
                if a2 and 0 < py2 < gh-1 and 0 < px2 < gw-1:
                    grid[py2][px2] = 3

                # Render
                scr.clear()
                draw_scores(scr, s1, s2, me, 0, cols)
                draw_box(scr, oy, ox, gh, gw)

                # Grid
                for y in range(1, gh-1):
                    for x in range(1, gw-1):
                        c = grid[y][x]
                        if c == 2:
                            scr.addch(oy+y, ox+x, '█', curses.color_pair(C_P1))
                        elif c == 3:
                            scr.addch(oy+y, ox+x, '█', curses.color_pair(C_P2))

                # Heads
                heads = ['▲','▼','◀','▶']
                if a1 and 0 < py1 < gh-1 and 0 < px1 < gw-1:
                    scr.addch(oy+py1, ox+px1, heads[d1], curses.color_pair(C_P1)|curses.A_BOLD)
                if a2 and 0 < py2 < gh-1 and 0 < px2 < gw-1:
                    scr.addch(oy+py2, ox+px2, heads[d2], curses.color_pair(C_P2)|curses.A_BOLD)

                # Crash X
                if not a1 and 0 < py1 < gh-1 and 0 < px1 < gw-1:
                    scr.addch(oy+py1, ox+px1, '✕', curses.color_pair(C_P1)|curses.A_BOLD)
                if not a2 and 0 < py2 < gh-1 and 0 < px2 < gw-1:
                    scr.addch(oy+py2, ox+px2, '✕', curses.color_pair(C_P2)|curses.A_BOLD)

                center(scr, rows-1, "WASD / Arrow / IJKL: 移動   Q: 終了", curses.color_pair(C_DIM)|curses.A_DIM)
                scr.refresh()

            elif t == "round_end":
                phase = "round_end"
                s1, s2 = msg["s1"], msg["s2"]
                w = msg["winner"]
                if w == 0: txt, clr = "DRAW!", C_TEXT
                elif (w == 1 and me == 1) or (w == 2 and me == 2): txt, clr = "★ YOU WIN! ★", C_WIN
                else: txt, clr = "★ YOU LOSE ★", C_DIM
                center(scr, rows//2, txt, curses.color_pair(clr)|curses.A_BOLD)
                center(scr, rows//2+2, f"P1 {s1} - {s2} P2", curses.color_pair(C_TEXT))
                scr.refresh()

            elif t == "match_end":
                phase = "match_end"
                s1, s2 = msg["s1"], msg["s2"]
                iwin = (s1 > s2 and me == 1) or (s2 > s1 and me == 2)
                scr.clear()

                if iwin:
                    center(scr, rows//2-3, "🏆  YOU WIN!  🏆", curses.color_pair(C_WIN)|curses.A_BOLD)
                else:
                    center(scr, rows//2-3, "💀  YOU LOSE  💀", curses.color_pair(C_DIM)|curses.A_BOLD)

                center(scr, rows//2-1, f"Final: P1 {s1} - {s2} P2", curses.color_pair(C_TEXT))
                center(scr, rows//2+1, f"(あなた: P{me})", curses.color_pair(C_DIM))
                center(scr, rows//2+4, "Press any key to exit", curses.color_pair(C_DIM)|curses.A_DIM)
                scr.refresh()
                scr.nodelay(False)
                scr.getch()
                return

    # Disconnected
    scr.clear()
    center(scr, rows//2, "接続が切断されました", curses.color_pair(C_DIM))
    scr.refresh()
    scr.nodelay(False)
    scr.getch()

# ===== MAIN =====
def main(scr):
    curses.curs_set(0)
    init_colors()

    while True:
        choice = show_title(scr)
        if choice == 'quit': return

        code = None
        if choice == 'join':
            code = get_room_code(scr)
            if not code: continue

        show_status(scr, "サーバーに接続中...", f"{SERVER}:{PORT}")

        try:
            net = NetClient(SERVER, PORT)
        except Exception as e:
            show_status(scr, "接続失敗！", str(e))
            scr.nodelay(False); scr.getch()
            continue

        if choice == 'match':
            net.send({"type":"match"})
            show_status(scr, "対戦相手を探しています...", "ランダムマッチング中")
        elif choice == 'create':
            net.send({"type":"create"})
            show_status(scr, "部屋を作成中...")
        elif choice == 'join':
            net.send({"type":"join","code":code})
            show_status(scr, f"部屋 {code} に接続中...")

        # Wait for match
        scr.nodelay(True); scr.timeout(100)
        me = None
        matched = False
        room_code = ""

        while net.alive and not matched:
            k = scr.getch()
            if k in (ord('q'), ord('Q'), 27):
                net.close(); break

            for msg in net.poll():
                if msg["type"] == "waiting":
                    show_status(scr, "対戦相手を探しています...", "ランダムマッチング中 (Q: キャンセル)")
                elif msg["type"] == "room_created":
                    room_code = msg["code"]
                    show_status(scr, f"ルームコード: {room_code}", "相手に伝えて！ (Q: キャンセル)")
                elif msg["type"] == "matched":
                    me = msg["player"]
                    room_code = msg.get("room","")
                    matched = True
                elif msg["type"] == "error":
                    show_status(scr, "エラー", msg.get("msg",""))
                    scr.nodelay(False); scr.getch()
                    net.close(); break

        if matched:
            show_status(scr, f"マッチ成立！ (P{me})", f"Room: {room_code}")
            time.sleep(1)
            game_loop(scr, net, me)

        net.close()

def entry():
    parser = argparse.ArgumentParser(description="/pvp - Claude Code Battle Arena")
    parser.add_argument('--server', default=SERVER, help='Server address')
    parser.add_argument('--port', type=int, default=PORT, help='Server port')
    parser.add_argument('--room', help='Join room code directly')
    parser.add_argument('--match', action='store_true', help='Quick match immediately')
    args = parser.parse_args()

    global SERVER, PORT
    SERVER = args.server
    PORT = args.port

    if args.match or args.room:
        # Direct mode: skip menu
        def direct(scr):
            curses.curs_set(0); init_colors()
            rows, cols = scr.getmaxyx()
            show_status(scr, "サーバーに接続中...", f"{SERVER}:{PORT}")
            try:
                net = NetClient(SERVER, PORT)
            except Exception as e:
                show_status(scr, "接続失敗！", str(e))
                scr.getch(); return

            if args.room:
                net.send({"type":"join","code":args.room.upper()})
                show_status(scr, f"部屋 {args.room.upper()} に接続中...")
            else:
                net.send({"type":"match"})
                show_status(scr, "対戦相手を探しています...")

            scr.nodelay(True); scr.timeout(100)
            me, matched = None, False
            while net.alive and not matched:
                k = scr.getch()
                if k in (ord('q'),ord('Q'),27): net.close(); return
                for msg in net.poll():
                    if msg["type"] == "matched":
                        me = msg["player"]; matched = True
                    elif msg["type"] == "room_created":
                        show_status(scr, f"ルームコード: {msg['code']}", "相手に伝えて！")
                    elif msg["type"] == "error":
                        show_status(scr, "エラー", msg.get("msg",""))
                        scr.nodelay(False); scr.getch(); net.close(); return
            if matched:
                game_loop(scr, net, me)
            net.close()
        curses.wrapper(direct)
    else:
        curses.wrapper(main)

if __name__ == '__main__':
    entry()
