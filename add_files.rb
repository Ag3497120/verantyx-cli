require 'xcodeproj'
project_path = 'cli/VerantyxIDE/Verantyx.xcodeproj'
project = Xcodeproj::Project.open(project_path)

# ターゲットの取得
target = project.targets.find { |t| t.name == 'Verantyx' }

# グループの取得 (VRBridge フォルダがあると仮定)
group = project.main_group.find_subpath('Verantyx/VRBridge', true)
guest_group = project.main_group.find_subpath('Verantyx/VRBridge/GuestOS', true)

# 追加するファイル
files_to_add = [
  { path: 'cli/VerantyxIDE/Sources/Verantyx/VRBridge/NetworkCompositor.swift', group: group },
  { path: 'cli/VerantyxIDE/Sources/Verantyx/VRBridge/JCrossVRProtocol.swift', group: group },
  { path: 'cli/VerantyxIDE/Sources/Verantyx/VRBridge/GuestOS/VisionClientCompositor.swift', group: guest_group }
]

files_to_add.each do |f|
  file_ref = f[:group].new_reference(File.expand_path(f[:path]))
  # ソースビルドフェーズに追加
  unless target.source_build_phase.files_references.include?(file_ref)
    target.source_build_phase.add_file_reference(file_ref)
    puts "Added #{f[:path]} to target Verantyx"
  else
    puts "#{f[:path]} is already in target Verantyx"
  end
end

project.save
