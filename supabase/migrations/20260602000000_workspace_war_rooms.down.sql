-- B2GOPS-004 down migration
DROP FUNCTION IF EXISTS ops_toggle_checklist_item;
DROP FUNCTION IF EXISTS ops_get_war_room;
DROP FUNCTION IF EXISTS ops_log_war_room_action;
DROP FUNCTION IF EXISTS ops_add_war_room_member;
DROP FUNCTION IF EXISTS ops_create_war_room;
DROP POLICY IF EXISTS "Room participants can insert log" ON workspace_war_room_log;
DROP POLICY IF EXISTS "Room participants can view log" ON workspace_war_room_log;
DROP POLICY IF EXISTS "Members can view member list" ON workspace_war_room_members;
DROP POLICY IF EXISTS "Room owner can manage members" ON workspace_war_room_members;
DROP POLICY IF EXISTS "Members can view war room" ON workspace_war_rooms;
DROP POLICY IF EXISTS "Owner can CRUD war room" ON workspace_war_rooms;
DROP TABLE IF EXISTS workspace_war_room_log;
DROP TABLE IF EXISTS workspace_war_room_members;
DROP TABLE IF EXISTS workspace_war_rooms;
