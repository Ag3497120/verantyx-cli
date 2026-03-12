//
//  ScheduleDetailView.swift
//  ScheduleApp
//
//  スケジュール詳細・編集画面
//

import SwiftUI

struct ScheduleDetailView: View {
    let schedule: Schedule
    @ObservedObject var viewModel: ScheduleViewModel
    @Environment(\.dismiss) var dismiss

    @State private var isEditing = false
    @State private var editedSchedule: Schedule
    @State private var showingDeleteAlert = false

    init(schedule: Schedule, viewModel: ScheduleViewModel) {
        self.schedule = schedule
        self.viewModel = viewModel
        _editedSchedule = State(initialValue: schedule)
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                if isEditing {
                    editingView
                } else {
                    detailView
                }
            }
            .padding()
        }
        .navigationTitle(isEditing ? "編集" : "詳細")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .navigationBarTrailing) {
                if isEditing {
                    Button("保存") {
                        saveChanges()
                    }
                } else {
                    Button("編集") {
                        isEditing = true
                    }
                }
            }
        }
    }

    // MARK: - 詳細表示ビュー
    private var detailView: some View {
        VStack(alignment: .leading, spacing: 20) {
            // タイトルと完了状態
            HStack {
                Text(schedule.title)
                    .font(.title)
                    .fontWeight(.bold)
                Spacer()
                Button(action: {
                    viewModel.toggleCompletion(schedule)
                    dismiss()
                }) {
                    Image(systemName: schedule.isCompleted ? "checkmark.circle.fill" : "circle")
                        .font(.title)
                        .foregroundColor(schedule.isCompleted ? .green : .gray)
                }
            }

            Divider()

            // 優先度
            HStack {
                Image(systemName: "flag.fill")
                    .foregroundColor(schedule.priority.color)
                Text("優先度")
                    .foregroundColor(.gray)
                Spacer()
                Text(schedule.priority.rawValue)
                    .fontWeight(.semibold)
                    .foregroundColor(schedule.priority.color)
            }

            // 日付
            HStack {
                Image(systemName: "calendar")
                    .foregroundColor(.blue)
                Text("日付")
                    .foregroundColor(.gray)
                Spacer()
                Text(schedule.dateString)
                    .fontWeight(.semibold)
            }

            // 時間
            HStack {
                Image(systemName: "clock")
                    .foregroundColor(.blue)
                Text("時間")
                    .foregroundColor(.gray)
                Spacer()
                Text(schedule.timeRangeString)
                    .fontWeight(.semibold)
            }

            // カテゴリ
            if !schedule.category.isEmpty {
                HStack {
                    Image(systemName: "tag")
                        .foregroundColor(.blue)
                    Text("カテゴリ")
                        .foregroundColor(.gray)
                    Spacer()
                    Text(schedule.category)
                        .fontWeight(.semibold)
                }
            }

            // 場所
            if !schedule.location.isEmpty {
                HStack {
                    Image(systemName: "location")
                        .foregroundColor(.blue)
                    Text("場所")
                        .foregroundColor(.gray)
                    Spacer()
                    Text(schedule.location)
                        .fontWeight(.semibold)
                }
            }

            // 説明
            if !schedule.description.isEmpty {
                VStack(alignment: .leading, spacing: 8) {
                    HStack {
                        Image(systemName: "doc.text")
                            .foregroundColor(.blue)
                        Text("説明")
                            .foregroundColor(.gray)
                    }
                    Text(schedule.description)
                        .padding()
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .background(Color.gray.opacity(0.1))
                        .cornerRadius(8)
                }
            }

            Divider()

            // 削除ボタン
            Button(action: {
                showingDeleteAlert = true
            }) {
                HStack {
                    Spacer()
                    Text("削除")
                        .fontWeight(.semibold)
                        .foregroundColor(.white)
                    Spacer()
                }
                .padding()
                .background(Color.red)
                .cornerRadius(10)
            }
            .alert("削除確認", isPresented: $showingDeleteAlert) {
                Button("キャンセル", role: .cancel) {}
                Button("削除", role: .destructive) {
                    viewModel.deleteSchedule(schedule)
                    dismiss()
                }
            } message: {
                Text("このスケジュールを削除してもよろしいですか?")
            }
        }
    }

    // MARK: - 編集ビュー
    private var editingView: some View {
        Form {
            Section(header: Text("基本情報")) {
                TextField("タイトル", text: $editedSchedule.title)
                TextField("説明", text: $editedSchedule.description)
                TextField("カテゴリ", text: $editedSchedule.category)
                TextField("場所", text: $editedSchedule.location)
            }

            Section(header: Text("日時")) {
                DatePicker("日付", selection: $editedSchedule.date, displayedComponents: .date)
                    .environment(\.locale, Locale(identifier: "ja_JP"))

                DatePicker("開始時刻", selection: $editedSchedule.startTime, displayedComponents: .hourAndMinute)
                    .environment(\.locale, Locale(identifier: "ja_JP"))

                DatePicker("終了時刻", selection: $editedSchedule.endTime, displayedComponents: .hourAndMinute)
                    .environment(\.locale, Locale(identifier: "ja_JP"))
            }

            Section(header: Text("優先度")) {
                Picker("優先度", selection: $editedSchedule.priority) {
                    ForEach(Priority.allCases, id: \.self) { priority in
                        HStack {
                            Circle()
                                .fill(priority.color)
                                .frame(width: 12, height: 12)
                            Text(priority.rawValue)
                        }
                        .tag(priority)
                    }
                }
                .pickerStyle(SegmentedPickerStyle())
            }

            Section {
                Button("キャンセル") {
                    editedSchedule = schedule
                    isEditing = false
                }
            }
        }
    }

    private func saveChanges() {
        viewModel.updateSchedule(editedSchedule)
        isEditing = false
    }
}

struct ScheduleDetailView_Previews: PreviewProvider {
    static var previews: some View {
        NavigationView {
            ScheduleDetailView(
                schedule: Schedule.sampleData[0],
                viewModel: ScheduleViewModel()
            )
        }
    }
}
