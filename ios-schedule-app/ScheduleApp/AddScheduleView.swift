//
//  AddScheduleView.swift
//  ScheduleApp
//
//  スケジュール追加画面
//

import SwiftUI

struct AddScheduleView: View {
    @ObservedObject var viewModel: ScheduleViewModel
    @Environment(\.dismiss) var dismiss

    @State private var title = ""
    @State private var description = ""
    @State private var date = Date()
    @State private var startTime = Date()
    @State private var endTime = Date().addingTimeInterval(3600)
    @State private var priority: Priority = .medium
    @State private var category = ""
    @State private var location = ""
    @State private var showingValidationError = false
    @State private var validationMessage = ""

    var body: some View {
        NavigationView {
            Form {
                Section(header: Text("基本情報")) {
                    TextField("タイトル", text: $title)
                    TextField("説明", text: $description)
                    TextField("カテゴリ", text: $category)
                    TextField("場所", text: $location)
                }

                Section(header: Text("日時")) {
                    DatePicker("日付", selection: $date, displayedComponents: .date)
                        .environment(\.locale, Locale(identifier: "ja_JP"))

                    DatePicker("開始時刻", selection: $startTime, displayedComponents: .hourAndMinute)
                        .environment(\.locale, Locale(identifier: "ja_JP"))

                    DatePicker("終了時刻", selection: $endTime, displayedComponents: .hourAndMinute)
                        .environment(\.locale, Locale(identifier: "ja_JP"))
                }

                Section(header: Text("優先度")) {
                    Picker("優先度", selection: $priority) {
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
                    Button(action: saveSchedule) {
                        HStack {
                            Spacer()
                            Text("保存")
                                .fontWeight(.semibold)
                            Spacer()
                        }
                    }
                }
            }
            .navigationTitle("新規スケジュール")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button("キャンセル") {
                        dismiss()
                    }
                }
            }
            .alert("入力エラー", isPresented: $showingValidationError) {
                Button("OK", role: .cancel) {}
            } message: {
                Text(validationMessage)
            }
        }
    }

    private func saveSchedule() {
        // バリデーション
        guard !title.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            validationMessage = "タイトルを入力してください"
            showingValidationError = true
            return
        }

        guard startTime < endTime else {
            validationMessage = "終了時刻は開始時刻より後に設定してください"
            showingValidationError = true
            return
        }

        let schedule = Schedule(
            title: title,
            description: description,
            date: date,
            startTime: startTime,
            endTime: endTime,
            priority: priority,
            category: category,
            location: location
        )

        viewModel.addSchedule(schedule)
        dismiss()
    }
}

struct AddScheduleView_Previews: PreviewProvider {
    static var previews: some View {
        AddScheduleView(viewModel: ScheduleViewModel())
    }
}
