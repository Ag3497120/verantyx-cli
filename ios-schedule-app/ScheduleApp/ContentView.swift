//
//  ContentView.swift
//  ScheduleApp
//
//  メインビュー
//

import SwiftUI

struct ContentView: View {
    @StateObject private var viewModel = ScheduleViewModel()
    @State private var showingAddSchedule = false

    var body: some View {
        NavigationView {
            VStack(spacing: 0) {
                // カレンダービュー
                CalendarView(selectedDate: $viewModel.selectedDate, viewModel: viewModel)
                    .padding()

                Divider()

                // 検索バー
                HStack {
                    Image(systemName: "magnifyingglass")
                        .foregroundColor(.gray)
                    TextField("検索", text: $viewModel.searchText)
                        .textFieldStyle(RoundedBorderTextFieldStyle())
                }
                .padding(.horizontal)
                .padding(.vertical, 8)

                // スケジュールリスト
                if viewModel.filteredSchedules.isEmpty {
                    VStack(spacing: 16) {
                        Image(systemName: "calendar.badge.exclamationmark")
                            .font(.system(size: 60))
                            .foregroundColor(.gray)
                        Text("スケジュールがありません")
                            .font(.headline)
                            .foregroundColor(.gray)
                    }
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                } else {
                    List {
                        ForEach(viewModel.filteredSchedules) { schedule in
                            NavigationLink(destination: ScheduleDetailView(schedule: schedule, viewModel: viewModel)) {
                                ScheduleRowView(schedule: schedule, viewModel: viewModel)
                            }
                        }
                        .onDelete(perform: viewModel.deleteSchedules)
                    }
                    .listStyle(PlainListStyle())
                }
            }
            .navigationTitle("スケジュール")
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button(action: {
                        showingAddSchedule = true
                    }) {
                        Image(systemName: "plus")
                    }
                }
            }
            .sheet(isPresented: $showingAddSchedule) {
                AddScheduleView(viewModel: viewModel)
            }
        }
    }
}

// MARK: - スケジュール行ビュー
struct ScheduleRowView: View {
    let schedule: Schedule
    @ObservedObject var viewModel: ScheduleViewModel

    var body: some View {
        HStack(spacing: 12) {
            // 完了チェックボックス
            Button(action: {
                viewModel.toggleCompletion(schedule)
            }) {
                Image(systemName: schedule.isCompleted ? "checkmark.circle.fill" : "circle")
                    .font(.title2)
                    .foregroundColor(schedule.isCompleted ? .green : .gray)
            }
            .buttonStyle(BorderlessButtonStyle())

            VStack(alignment: .leading, spacing: 4) {
                HStack {
                    Text(schedule.title)
                        .font(.headline)
                        .strikethrough(schedule.isCompleted)
                    Spacer()
                    Text(schedule.priority.rawValue)
                        .font(.caption)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 4)
                        .background(schedule.priority.color.opacity(0.2))
                        .foregroundColor(schedule.priority.color)
                        .cornerRadius(8)
                }

                Text(schedule.timeRangeString)
                    .font(.subheadline)
                    .foregroundColor(.gray)

                if !schedule.category.isEmpty {
                    Text(schedule.category)
                        .font(.caption)
                        .padding(.horizontal, 6)
                        .padding(.vertical, 2)
                        .background(Color.blue.opacity(0.2))
                        .foregroundColor(.blue)
                        .cornerRadius(4)
                }
            }
        }
        .padding(.vertical, 4)
        .opacity(schedule.isCompleted ? 0.6 : 1.0)
    }
}

// MARK: - カレンダービュー
struct CalendarView: View {
    @Binding var selectedDate: Date
    @ObservedObject var viewModel: ScheduleViewModel
    @State private var currentMonth: Date = Date()

    private let calendar = Calendar.current
    private let daysOfWeek = ["日", "月", "火", "水", "木", "金", "土"]

    var body: some View {
        VStack(spacing: 12) {
            // 月選択ヘッダー
            HStack {
                Button(action: {
                    changeMonth(by: -1)
                }) {
                    Image(systemName: "chevron.left")
                        .font(.title2)
                }

                Spacer()

                Text(monthYearString)
                    .font(.title2)
                    .fontWeight(.bold)

                Spacer()

                Button(action: {
                    changeMonth(by: 1)
                }) {
                    Image(systemName: "chevron.right")
                        .font(.title2)
                }
            }

            // 曜日ヘッダー
            HStack(spacing: 0) {
                ForEach(daysOfWeek, id: \.self) { day in
                    Text(day)
                        .font(.caption)
                        .fontWeight(.bold)
                        .frame(maxWidth: .infinity)
                        .foregroundColor(day == "日" ? .red : day == "土" ? .blue : .primary)
                }
            }

            // カレンダーグリッド
            LazyVGrid(columns: Array(repeating: GridItem(.flexible()), count: 7), spacing: 8) {
                ForEach(daysInMonth, id: \.self) { date in
                    if let date = date {
                        DayCell(
                            date: date,
                            isSelected: calendar.isDate(date, inSameDayAs: selectedDate),
                            isToday: calendar.isDateInToday(date),
                            hasSchedule: viewModel.hasSchedule(on: date),
                            scheduleCount: viewModel.scheduleCount(on: date)
                        )
                        .onTapGesture {
                            selectedDate = date
                        }
                    } else {
                        Color.clear
                            .frame(height: 40)
                    }
                }
            }
        }
    }

    private var monthYearString: String {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy年 M月"
        formatter.locale = Locale(identifier: "ja_JP")
        return formatter.string(from: currentMonth)
    }

    private var daysInMonth: [Date?] {
        guard let monthInterval = calendar.dateInterval(of: .month, for: currentMonth),
              let monthFirstWeek = calendar.dateInterval(of: .weekOfMonth, for: monthInterval.start) else {
            return []
        }

        var days: [Date?] = []
        var date = monthFirstWeek.start

        while days.count < 42 {
            if calendar.isDate(date, equalTo: currentMonth, toGranularity: .month) {
                days.append(date)
            } else {
                days.append(nil)
            }
            date = calendar.date(byAdding: .day, value: 1, to: date)!
        }

        return days
    }

    private func changeMonth(by value: Int) {
        if let newMonth = calendar.date(byAdding: .month, value: value, to: currentMonth) {
            currentMonth = newMonth
        }
    }
}

// MARK: - 日付セル
struct DayCell: View {
    let date: Date
    let isSelected: Bool
    let isToday: Bool
    let hasSchedule: Bool
    let scheduleCount: Int

    private let calendar = Calendar.current

    var body: some View {
        VStack(spacing: 2) {
            Text("\(calendar.component(.day, from: date))")
                .font(.system(size: 16))
                .fontWeight(isToday ? .bold : .regular)
                .foregroundColor(textColor)
                .frame(width: 36, height: 36)
                .background(backgroundColor)
                .cornerRadius(18)

            if hasSchedule {
                Circle()
                    .fill(Color.blue)
                    .frame(width: 6, height: 6)
            }
        }
        .frame(height: 50)
    }

    private var textColor: Color {
        if isSelected {
            return .white
        } else if isToday {
            return .blue
        } else {
            let weekday = calendar.component(.weekday, from: date)
            if weekday == 1 {
                return .red
            } else if weekday == 7 {
                return .blue
            } else {
                return .primary
            }
        }
    }

    private var backgroundColor: Color {
        if isSelected {
            return .blue
        } else if isToday {
            return .blue.opacity(0.2)
        } else {
            return .clear
        }
    }
}

struct ContentView_Previews: PreviewProvider {
    static var previews: some View {
        ContentView()
    }
}
