// Pure command-builder tests; never dispatch to a real compositor.
// Author: ae Orland
// GitHub: https://github.com/ae-orlando
#include <cassert>
#include <iostream>

#include "util/hyprland_workspace_command.hpp"

int main() {
  using waybar::util::hyprlandWorkspaceCommand;
  using waybar::util::quoteLua;
  assert(hyprlandWorkspaceCommand(2, "2", false, true) ==
         "dispatch hl.dsp.focus({workspace=\"2\",on_current_monitor=true})");
  assert(hyprlandWorkspaceCommand(3, "3", false, false) ==
         "dispatch hl.dsp.focus({workspace=\"3\",on_current_monitor=false})");
  assert(hyprlandWorkspaceCommand(-3, "work", false, true) ==
         "dispatch hl.dsp.focus({workspace=\"name:work\",on_current_monitor=true})");
  assert(hyprlandWorkspaceCommand(-3, "夜", false, false) ==
         "dispatch hl.dsp.focus({workspace=\"name:夜\",on_current_monitor=false})");
  assert(hyprlandWorkspaceCommand(-98, "magic", true, true) ==
         "dispatch hl.dsp.workspace.toggle_special(\"magic\")");
  assert(hyprlandWorkspaceCommand(-99, "special", true, false) ==
         "dispatch hl.dsp.workspace.toggle_special(\"\")");
  assert(quoteLua("a\"b\\c") == "\"a\\\"b\\\\c\"");
  assert(quoteLua("a\nb\r\t") == "\"a\\010b\\013\\009\"");
  assert(quoteLua(std::string(1, '\1') + "23") == "\"\\00123\"");
  assert(quoteLua("\"); hl.dispatch(hl.dsp.exit()); --") ==
         "\"\\\"); hl.dispatch(hl.dsp.exit()); --\"");
  std::cout << "PASS: 10 numeric/named/special workspace and Lua-escaping fixtures\n";
}
