create table NewPublicStreams (StreamName text primary key, Subscribed integer not null);
insert into NewPublicStreams(StreamName, Subscribed) select StreamName, 1 from PublicStreams;
drop table PublicStreams;
alter table NewPublicStreams rename to PublicStreams;
