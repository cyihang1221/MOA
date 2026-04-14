function tab = subsetTable( tab, field, values )
%tab = subsetTable( tab, field, values )
% the rows that match 'values' in field 'field' are kept
% Example: 
%     tab = subsetTable( tab, 'nr', [1 3 5] ) 
% 

%by: Magnus Åberg

tf = ismember( tab.( field ), values );

tab = maskTable( tab, tf );