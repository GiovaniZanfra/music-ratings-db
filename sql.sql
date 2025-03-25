-- Create artists table
CREATE TABLE artists (
    artist_id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    genre TEXT
);

-- Create albums table
CREATE TABLE albums (
    album_id SERIAL PRIMARY KEY,
    artist_id INT REFERENCES artists(artist_id),
    name TEXT NOT NULL,
    release_date DATE
);

-- Create tracks table
CREATE TABLE tracks (
    track_id SERIAL PRIMARY KEY,
    album_id INT REFERENCES albums(album_id),
    name TEXT NOT NULL,
    duration INT
);

-- Create ratings table
CREATE TABLE ratings (
    rating_id SERIAL PRIMARY KEY,
    track_id INT REFERENCES tracks(track_id),
    rating INT CHECK (rating BETWEEN 1 AND 10),
    review TEXT
);
