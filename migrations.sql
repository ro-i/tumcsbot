create table NewAlerts (Phrase text primary key, Emoji text not null);
insert into NewAlerts(Phrase, Emoji) select Phrase, Emoji from Alerts;
drop table Alerts;
alter table NewAlerts rename to Alerts;

create table NewMessages (MsgId text primary key, MsgText text not null);
insert into NewMessages(MsgId, MsgText) select Id, Text from Messages;
drop table Messages;
alter table NewMessages rename to Messages;
