# WebSocketClient — T16 godot-ws-client (T19 live: client handshake added)
#
# Thin WebSocket client. Responsibilities:
#   1. Maintain a connection to the G-GEAR gateway at ``ws_url``
#   2. Send the required client ``HandshakeMsg`` as the first frame so the T14
#      gateway transitions AWAITING_HANDSHAKE → ACTIVE before ``HANDSHAKE_TIMEOUT_S``
#   3. Auto-reconnect every ``RECONNECT_DELAY`` seconds on disconnect
#   4. Parse each incoming UTF-8 JSON frame into a Dictionary
#   5. Emit ``envelope_received`` / ``connection_status_changed``
#
# This script intentionally knows nothing about ControlEnvelope kinds or
# downstream dispatch. ``EnvelopeRouter.gd`` handles kind-based routing,
# keeping this client focused on transport concerns only. Fixture replay
# lives in the developer-only ``scripts/dev/FixturePlayer.gd`` so no test
# code leaks into the production path.
class_name WebSocketClient
extends Node

## WebSocket URL for the G-GEAR gateway (LAN address, no auth per architecture §6).
##
## Default resolves ``g-gear.local`` via mDNS or /etc/hosts. If that fails on the
## host OS, override this export in the Inspector (MainScene ▸ WebSocketClient)
## with the LAN IP the gateway is bound to, e.g. ``ws://192.168.3.85:8000/ws/observe``.
@export var ws_url: String = "ws://g-gear.local:8000/ws/observe"
## Schema version this client advertises in its client HandshakeMsg. Must match the
## gateway's :data:`erre_sandbox.schemas.SCHEMA_VERSION` or the gateway closes with
## ``ErrorMsg code="schema_mismatch"``.
const CLIENT_SCHEMA_VERSION: String = "0.1.0-m2"
## Reconnect delay in seconds. Set to 2.0s to satisfy MVP M2 acceptance criterion
## "WS 切断で 3 秒以内自動再接続" (MASTER-PLAN §4.4). See godot-gdscript patterns.md §1.
const RECONNECT_DELAY: float = 2.0
## Upper bound for a single incoming WebSocket frame. Anything larger is dropped
## with a warning — defends the headless Godot process against a misbehaving
## gateway that emits oversize JSON (see security review HIGH #1 for context).
const MAX_FRAME_BYTES: int = 1_048_576

var _ws: WebSocketPeer = WebSocketPeer.new()
var _connected: bool = false
var _handshake_sent: bool = false
var _should_reconnect: bool = false
var _reconnect_timer: float = 0.0

signal envelope_received(envelope: Dictionary)
signal connection_status_changed(connected: bool)


func _ready() -> void:
	_connect_to_server()


func _connect_to_server() -> void:
	_should_reconnect = false
	_handshake_sent = false
	print("[WS] connecting to %s" % ws_url)
	var err := _ws.connect_to_url(ws_url)
	if err != OK:
		push_warning(
			"[WS] connect_to_url failed (%s); retry in %ss"
			% [error_string(err), RECONNECT_DELAY]
		)
		_schedule_reconnect()


## Build the client HandshakeMsg JSON the T14 gateway expects as the first frame
## (must arrive within ``HANDSHAKE_TIMEOUT_S = 5.0`` or the session is closed).
func _send_client_handshake() -> void:
	var payload := {
		"kind": "handshake",
		"schema_version": CLIENT_SCHEMA_VERSION,
		"tick": 0,
		"sent_at": Time.get_datetime_string_from_system(true) + "Z",
		"peer": "godot",
		"capabilities": [],
	}
	var err := _ws.send_text(JSON.stringify(payload))
	if err != OK:
		push_warning("[WS] client handshake send failed: %s" % error_string(err))
	else:
		_handshake_sent = true
		print("[WS] client HandshakeMsg sent")


func _schedule_reconnect() -> void:
	_should_reconnect = true
	_reconnect_timer = RECONNECT_DELAY


func _process(delta: float) -> void:
	if _should_reconnect:
		_reconnect_timer -= delta
		if _reconnect_timer <= 0.0:
			_connect_to_server()
		return

	_ws.poll()
	var state := _ws.get_ready_state()
	match state:
		WebSocketPeer.STATE_OPEN:
			if not _connected:
				_connected = true
				print("[WS] connected to %s" % ws_url)
				connection_status_changed.emit(true)
			if not _handshake_sent:
				_send_client_handshake()
			_consume_packets()
		WebSocketPeer.STATE_CLOSING:
			pass
		WebSocketPeer.STATE_CLOSED:
			if _connected:
				_connected = false
				var code := _ws.get_close_code()
				var reason := _ws.get_close_reason()
				print("[WS] disconnected: code=%d reason=%s" % [code, reason])
				connection_status_changed.emit(false)
			_schedule_reconnect()


func _consume_packets() -> void:
	while _ws.get_available_packet_count() > 0:
		var packet := _ws.get_packet()
		if packet.size() > MAX_FRAME_BYTES:
			push_warning(
				"[WS] dropping oversize frame: %d bytes > %d" % [packet.size(), MAX_FRAME_BYTES]
			)
			continue
		var raw := packet.get_string_from_utf8()
		var parsed: Variant = JSON.parse_string(raw)
		if parsed is Dictionary:
			envelope_received.emit(parsed)
		else:
			# c_escape keeps stray control bytes (e.g. from a malformed UTF-8
			# frame) from breaking terminal output or log parsing.
			push_warning("[WS] malformed frame (not a JSON dict): %s" % raw.left(200).c_escape())
